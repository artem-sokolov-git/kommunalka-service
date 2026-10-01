import os
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event

DEFAULT_DATABASE_URL = "sqlite:///kommunalka.db"


def database_url() -> str:
    return os.environ.get("KOMMUNALKA_DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(connection: SQLiteConnection, _record: Any) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()
