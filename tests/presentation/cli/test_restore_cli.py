from pathlib import Path

import pytest

from kommunalka.infrastructure.backup.backup import push_dump
from kommunalka.infrastructure.backup.github import GitHubFile
from kommunalka.infrastructure.config import get_settings
from kommunalka.presentation.cli.restore import main
from tests.infrastructure.backup.conftest import FakeGitHub, add_reading, values


def restore_on_start(target: Path, github: FakeGitHub, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOMMUNALKA_DATABASE_URL", f"sqlite:///{target}")
    monkeypatch.setenv("KOMMUNALKA_DB_BACKUP_REPO_URL", "owner/backups")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_GITHUB_TOKEN", FakeGitHub.TOKEN)
    monkeypatch.setenv("KOMMUNALKA_GITHUB_API_URL", github.url)
    monkeypatch.setattr("sys.argv", ["restore", "--if-missing"])
    get_settings.cache_clear()
    try:
        main()
    finally:
        get_settings.cache_clear()


def test_restores_a_missing_database_on_start(
    database: Path,
    github: FakeGitHub,
    backup_file: GitHubFile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    push_dump(database, backup_file)
    target = tmp_path / "new" / "kommunalka.db"

    restore_on_start(target, github, monkeypatch)

    assert values(target) == ["41768"]


def test_keeps_an_existing_database_on_start(
    database: Path, github: FakeGitHub, backup_file: GitHubFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    push_dump(database, backup_file)
    add_reading(database, "41800")

    restore_on_start(database, github, monkeypatch)

    assert values(database) == ["41768", "41800"]
    assert list(database.parent.glob("*-before-restore-*")) == []


def test_starts_without_a_database_when_there_are_no_backups(
    github: FakeGitHub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "kommunalka.db"

    restore_on_start(target, github, monkeypatch)

    assert not target.exists()
