import sqlite3
from pathlib import Path

import pytest

from kommunalka.config import get_settings
from kommunalka.infrastructure.db.backup import BackupError, backup, push_dump
from kommunalka.infrastructure.db.github import GitHubFile
from kommunalka.infrastructure.db.restore import (
    fetch_dump,
    list_backups,
    main,
    restore_copy,
    restore_dump,
)
from tests.infrastructure.conftest import FakeGitHub


def values(database: Path) -> list[str]:
    connection = sqlite3.connect(database)
    try:
        return [value for (value,) in connection.execute("SELECT value FROM readings")]
    finally:
        connection.close()


def add_reading(database: Path, value: str) -> None:
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO readings VALUES (?)", (value,))
    connection.commit()
    connection.close()


def test_restores_latest_dump_from_github(
    database: Path, backup_file: GitHubFile, tmp_path: Path
) -> None:
    push_dump(database, backup_file)
    add_reading(database, "41800")
    push_dump(database, backup_file)
    target = tmp_path / "new" / "kommunalka.db"

    restore_dump(fetch_dump(backup_file), target)

    assert values(target) == ["41768", "41800"]


def test_restores_an_older_revision(
    database: Path, github: FakeGitHub, backup_file: GitHubFile
) -> None:
    push_dump(database, backup_file)
    first = github.commits[0]["sha"][:7]
    add_reading(database, "41800")
    push_dump(database, backup_file)

    restore_dump(fetch_dump(backup_file, first), database)

    assert values(database) == ["41768"]


def test_keeps_the_replaced_database(database: Path, tmp_path: Path) -> None:
    copy = backup(database, tmp_path / "backups", keep=5)
    add_reading(database, "99999")

    previous = restore_copy(copy, database)

    assert values(database) == ["41768"]
    assert previous is not None
    assert values(previous) == ["41768", "99999"]
    assert previous.name.startswith("kommunalka-before-restore-")


def test_broken_dump_leaves_the_database_alone(database: Path) -> None:
    with pytest.raises(BackupError, match="broken or empty"):
        restore_dump("", database)

    assert values(database) == ["41768"]
    assert not database.with_name("kommunalka.db.restoring").exists()


def test_empty_repository_has_nothing_to_restore(backup_file: GitHubFile) -> None:
    with pytest.raises(BackupError, match=r"No kommunalka\.sql in owner/backups yet"):
        fetch_dump(backup_file)


def test_lists_backups_newest_first(database: Path, backup_file: GitHubFile) -> None:
    push_dump(database, backup_file)
    add_reading(database, "41800")
    push_dump(database, backup_file)

    lines = list_backups(backup_file).splitlines()

    assert len(lines) == 2
    assert lines[0].startswith("0000002  2026-10-02T00:00:00Z  Backup ")


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
