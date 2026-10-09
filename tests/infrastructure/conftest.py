import sqlite3
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import Engine

from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork


@pytest.fixture
def uow(engine: Engine) -> SqlUnitOfWork:
    return SqlUnitOfWork(engine)


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """A small SQLite database file to back up and restore."""
    path = tmp_path / "kommunalka.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE readings (value TEXT)")
    connection.execute("INSERT INTO readings VALUES ('41768')")
    connection.commit()
    connection.close()
    return path


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """An empty bare git repository standing in for the backup repository on GitHub."""
    path = tmp_path / "backups.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(path)], check=True)
    return path
