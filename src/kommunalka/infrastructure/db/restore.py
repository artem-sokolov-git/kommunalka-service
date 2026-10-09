"""Restore the SQLite database from the GitHub backup repository or a local copy.

Usage: python -m kommunalka.infrastructure.db.restore [--revision REV | --file PATH | --list]

By default the latest dump in `db_backup_repo_url` is downloaded through the GitHub API and
restored into the database of `database_url`. The new database is built and checked aside
first; the replaced one is kept next to it as `<name>-before-restore-<time>.db`. Stop the app
before restoring.
"""

import argparse
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import make_url

from kommunalka.config import get_settings
from kommunalka.infrastructure.db.backup import BackupError, backup_file
from kommunalka.infrastructure.db.github import GitHubError, GitHubFile


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


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Restore the kommunalka database.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--revision", default="", help="commit to restore (default: latest)")
    source.add_argument("--file", type=Path, help="a local copy (.db) or dump (.sql) instead")
    source.add_argument("--list", action="store_true", help="list backups in the repository")
    parser.add_argument("--database", type=Path, default=make_url(settings.database_url).database)
    parser.add_argument("--repo", default=settings.db_backup_repo_url)
    args = parser.parse_args()
    if args.database is None:
        parser.error(f"no database file in {settings.database_url}")
    if args.file is None and not args.repo:
        parser.error("no backup repository: set KOMMUNALKA_DB_BACKUP_REPO_URL or pass --file")
    try:
        if args.list:
            print(list_backups(backup_file(settings, args.repo)), end="")
            return
        if args.file is not None:
            origin = str(args.file)
            if args.file.suffix == ".sql":
                previous = restore_dump(args.file.read_text(), args.database)
            else:
                previous = restore_copy(args.file, args.database)
        else:
            file = backup_file(settings, args.repo)
            origin = f"{file.repo} at {args.revision or file.branch}"
            previous = restore_dump(fetch_dump(file, args.revision or None), args.database)
    except (BackupError, GitHubError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"restored {args.database} from {origin}")
    if previous is not None:
        print(f"the previous database is kept in {previous}")


if __name__ == "__main__":
    main()
