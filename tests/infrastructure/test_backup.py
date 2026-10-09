import sqlite3
import subprocess
from pathlib import Path

import pytest

from kommunalka.config import get_settings
from kommunalka.infrastructure.db.backup import BackupError, backup, main, push_dump


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


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    path = tmp_path / "backups.git"
    git("init", "--quiet", "--bare", str(path))
    return path


def test_pushes_a_dump_to_git(database: Path, remote: Path, tmp_path: Path) -> None:
    assert push_dump(database, tmp_path / "clone", str(remote))

    dump = git("--git-dir", str(remote), "show", "main:kommunalka.sql")
    assert "INSERT INTO \"readings\" VALUES('41768');" in dump


def test_commits_only_changes(database: Path, remote: Path, tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    push_dump(database, clone, str(remote))

    assert not push_dump(database, clone, str(remote))
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO readings VALUES ('41800')")
    connection.commit()
    connection.close()
    assert push_dump(database, clone, str(remote))

    assert len(git("--git-dir", str(remote), "log", "--oneline", "main").splitlines()) == 2


def test_unreachable_remote_is_an_error(database: Path, tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="git clone failed"):
        push_dump(database, tmp_path / "clone", str(tmp_path / "missing.git"))


def test_cli_takes_everything_from_settings(
    database: Path, remote: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KOMMUNALKA_DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_DIR", str(tmp_path / "copies"))
    monkeypatch.setenv("KOMMUNALKA_DB_BACKUP_REPO_URL", str(remote))
    monkeypatch.setenv("KOMMUNALKA_DB_BACKUP_REPO_DIR", str(tmp_path / "clone"))
    monkeypatch.setattr("sys.argv", ["backup"])
    get_settings.cache_clear()
    try:
        main()
    finally:
        get_settings.cache_clear()

    assert len(list((tmp_path / "copies").glob("kommunalka-*.db"))) == 1
    assert "41768" in git("--git-dir", str(remote), "show", "main:kommunalka.sql")
