import sqlite3
from pathlib import Path

import pytest

from kommunalka.infrastructure.backup.backup import BackupError, backup, push_dump
from kommunalka.infrastructure.backup.github import GitHubError, GitHubFile, repo_name
from tests.infrastructure.backup.conftest import FakeGitHub


def test_copies_database(database: Path, tmp_path: Path) -> None:
    copy = backup(database, tmp_path / "backups", keep=5)

    connection = sqlite3.connect(copy)
    assert connection.execute("SELECT value FROM readings").fetchall() == [("41768",)]
    connection.close()


def test_keeps_newest_copies(database: Path, tmp_path: Path) -> None:
    directory = tmp_path / "backups"
    directory.mkdir()
    for day in range(1, 5):
        (directory / f"kommunalka-2026010{day}-000000.db").touch()

    newest = backup(database, directory, keep=2)

    assert sorted(directory.iterdir()) == [directory / "kommunalka-20260104-000000.db", newest]


def test_missing_database_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        backup(tmp_path / "missing.db", tmp_path / "backups", keep=5)

    assert not (tmp_path / "missing.db").exists()


def add_reading(database: Path, value: str) -> None:
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO readings VALUES (?)", (value,))
    connection.commit()
    connection.close()


def test_pushes_a_dump_to_github(
    database: Path, github: FakeGitHub, backup_file: GitHubFile
) -> None:
    assert push_dump(database, backup_file)

    [commit] = github.commits
    assert "INSERT INTO \"readings\" VALUES('41768');" in commit["files"]["kommunalka.sql"]
    assert commit["message"].startswith("Backup ")


def test_commits_only_changes(database: Path, github: FakeGitHub, backup_file: GitHubFile) -> None:
    push_dump(database, backup_file)

    assert not push_dump(database, backup_file)
    add_reading(database, "41800")
    assert push_dump(database, backup_file)

    assert len(github.commits) == 2


def test_rejected_token_is_an_error(database: Path, github: FakeGitHub) -> None:
    file = GitHubFile("owner/backups", "kommunalka.sql", token="wrong", api_url=github.url)

    with pytest.raises(GitHubError, match="401 Bad credentials"):
        push_dump(database, file)


@pytest.mark.parametrize(
    "repo",
    ["owner/backups", "https://github.com/owner/backups", "https://github.com/owner/backups.git"],
)
def test_reads_repository_name(repo: str) -> None:
    assert repo_name(repo) == "owner/backups"
