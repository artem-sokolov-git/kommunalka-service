"""Restore the SQLite database from a dump or a local copy.

The new database is built and checked aside first; the replaced one is kept next to it as
`<name>-before-restore-<time>.db`.
"""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from kommunalka.infrastructure.backup.backup import BackupError
from kommunalka.infrastructure.backup.github import GitHubFile


def restore_dump(dump: str, database: Path) -> Path | None:
    """Replace `database` with one built from an SQL `dump`; return where the old one went."""
    return _replace(database, lambda connection: connection.executescript(dump))


def restore_copy(copy: Path, database: Path) -> Path | None:
    """Replace `database` with a copy of the database file `copy`; return where the old one went."""
    if not copy.is_file():
        raise BackupError(f"{copy} not found")

    def fill(connection: sqlite3.Connection) -> None:
        source = sqlite3.connect(copy)
        try:
            source.backup(connection)
        finally:
            source.close()

    return _replace(database, fill)


def fetch_dump(file: GitHubFile, revision: str | None = None) -> str:
    """The dump in the backup repository at `revision` (default: the latest)."""
    dump = file.read(revision)
    if dump is None:
        where = f"at {revision}" if revision else "yet"
        raise BackupError(f"No {file.path} in {file.repo} {where}")
    return dump


def list_backups(file: GitHubFile) -> str:
    return "".join(
        f"{revision.sha[:7]}  {revision.date}  {revision.message}\n" for revision in file.history()
    )


def _replace(database: Path, fill: Callable[[sqlite3.Connection], object]) -> Path | None:
    database.parent.mkdir(parents=True, exist_ok=True)
    new = database.with_name(f"{database.name}.restoring")
    new.unlink(missing_ok=True)
    connection = sqlite3.connect(new)
    try:
        fill(connection)
        connection.commit()
        [result] = connection.execute("PRAGMA integrity_check").fetchone()
        [tables] = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()
    finally:
        connection.close()
    if result != "ok" or not tables:
        new.unlink()
        raise BackupError(f"Restored database is broken or empty: {result}")
    previous = None
    if database.exists():
        previous = database.with_name(
            f"{database.stem}-before-restore-{datetime.now(UTC):%Y%m%d-%H%M%S}Z.db"
        )
        database.replace(previous)
    new.replace(database)
    return previous
