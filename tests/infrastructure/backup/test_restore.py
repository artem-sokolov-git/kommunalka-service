from pathlib import Path

import pytest

from kommunalka.infrastructure.backup.backup import BackupError, backup, push_dump
from kommunalka.infrastructure.backup.github import GitHubFile
from kommunalka.infrastructure.backup.restore import (
    fetch_dump,
    list_backups,
    restore_copy,
    restore_dump,
)
from tests.infrastructure.backup.conftest import FakeGitHub, add_reading, values


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
