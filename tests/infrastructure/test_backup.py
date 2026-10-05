import sqlite3
from pathlib import Path

import pytest

from kommunalka.infrastructure.db.backup import BackupError, backup


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "kommunalka.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE readings (value TEXT)")
    connection.execute("INSERT INTO readings VALUES ('41768')")
    connection.commit()
    connection.close()
    return path


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
