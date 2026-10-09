"""Restore the SQLite database from the git backup repository or a local copy.

Usage: python -m kommunalka.infrastructure.db.restore [--revision REV | --file PATH | --list]

By default the latest dump from `db_backup_repo_url` (cloned into `db_backup_repo_dir`) is
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
from kommunalka.infrastructure.db.backup import DUMP, BackupError, run_git


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


def fetch_dump(
    clone: Path, remote: str, *, token: str | None = None, branch: str = "main", revision: str = ""
) -> tuple[str, str]:
    """Return a dump from the backup repository and a description of its commit.

    Without `revision`, the newest backup: the remote branch, or the local clone if it holds
    backups that were not pushed yet.
    """
    if (clone / ".git").is_dir():
        run_git(clone, token, "fetch", "--quiet", "origin")
    else:
        run_git(None, token, "clone", "--quiet", remote, str(clone))
    if not revision:
        remote_head = f"origin/{branch}"
        if run_git(
            clone, token, "rev-parse", "--verify", "--quiet", remote_head, check=False
        ).returncode:
            raise BackupError(f"No backups in {remote} yet")
        ahead = run_git(
            clone, token, "merge-base", "--is-ancestor", remote_head, "HEAD", check=False
        )
        revision = "HEAD" if ahead.returncode == 0 else remote_head
    dump = run_git(clone, token, "show", f"{revision}:{DUMP}").stdout
    commit = run_git(clone, token, "log", "-1", "--format=%h %s", revision).stdout.strip()
    return dump, commit


def list_backups(
    clone: Path, remote: str, *, token: str | None = None, branch: str = "main"
) -> str:
    fetch_dump(clone, remote, token=token, branch=branch)
    return run_git(
        clone, token, "log", "-20", "--format=%h  %s", f"origin/{branch}", "--", DUMP
    ).stdout


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
    source.add_argument("--revision", default="", help="git commit to restore (default: latest)")
    source.add_argument("--file", type=Path, help="a local copy (.db) or dump (.sql) instead")
    source.add_argument("--list", action="store_true", help="list backups in the repository")
    parser.add_argument("--database", type=Path, default=make_url(settings.database_url).database)
    parser.add_argument("--git-remote", default=settings.db_backup_repo_url)
    parser.add_argument("--git-dir", type=Path, default=settings.db_backup_repo_dir)
    args = parser.parse_args()
    if args.database is None:
        parser.error(f"no database file in {settings.database_url}")
    if args.file is None and not args.git_remote:
        parser.error("no backup repository: set KOMMUNALKA_DB_BACKUP_REPO_URL or pass --file")
    secret = settings.backup_github_token
    token = secret.get_secret_value() if secret else None
    branch = settings.db_backup_branch
    try:
        if args.list:
            print(list_backups(args.git_dir, args.git_remote, token=token, branch=branch), end="")
            return
        if args.file is not None:
            origin = str(args.file)
            if args.file.suffix == ".sql":
                previous = restore_dump(args.file.read_text(), args.database)
            else:
                previous = restore_copy(args.file, args.database)
        else:
            dump, origin = fetch_dump(
                args.git_dir, args.git_remote, token=token, branch=branch, revision=args.revision
            )
            previous = restore_dump(dump, args.database)
    except BackupError as error:
        parser.exit(1, f"error: {error}\n")
    print(f"restored {args.database} from {origin}")
    if previous is not None:
        print(f"the previous database is kept in {previous}")


if __name__ == "__main__":
    main()
