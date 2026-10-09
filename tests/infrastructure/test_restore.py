import sqlite3
import subprocess
from pathlib import Path

import pytest

from kommunalka.infrastructure.db.backup import BackupError, backup, push_dump
from kommunalka.infrastructure.db.restore import (
    fetch_dump,
    list_backups,
    restore_copy,
    restore_dump,
)


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


def test_restores_latest_dump_from_git(database: Path, remote: Path, tmp_path: Path) -> None:
    push_dump(database, tmp_path / "clone", str(remote))
    add_reading(database, "41800")
    push_dump(database, tmp_path / "clone", str(remote))
    target = tmp_path / "new" / "kommunalka.db"

    dump, commit = fetch_dump(tmp_path / "fresh-clone", str(remote))
    restore_dump(dump, target)

    assert values(target) == ["41768", "41800"]
    assert "Backup" in commit


def test_restores_an_older_revision(database: Path, remote: Path, tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    push_dump(database, clone, str(remote))
    first = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    add_reading(database, "41800")
    push_dump(database, clone, str(remote))

    dump, _ = fetch_dump(clone, str(remote), revision=first)
    restore_dump(dump, database)

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


def test_empty_repository_has_nothing_to_restore(remote: Path, tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="No backups"):
        fetch_dump(tmp_path / "clone", str(remote))


def test_lists_backups(database: Path, remote: Path, tmp_path: Path) -> None:
    push_dump(database, tmp_path / "clone", str(remote))
    add_reading(database, "41800")
    push_dump(database, tmp_path / "clone", str(remote))

    assert len(list_backups(tmp_path / "other-clone", str(remote)).splitlines()) == 2
