"""Online backup of the SQLite database with rotation, optionally pushed to GitHub.

Usage: python -m kommunalka.infrastructure.db.backup [--every SECONDS] [...]

Everything comes from the settings (`kommunalka.config`): the database of `database_url`,
copies in `backup_dir`. With `db_backup_repo_url`, a text dump of the database is also
committed to that GitHub repository through its API; the history of the file is the history
of backups. Options override the settings for one run.
"""

import argparse
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import make_url

from kommunalka.config import Settings, get_settings
from kommunalka.infrastructure.db.github import GitHubError, GitHubFile

PREFIX = "kommunalka-"
DUMP = "kommunalka.sql"


class BackupError(Exception):
    pass


def backup(database: Path, directory: Path, *, keep: int) -> Path:
    """Copy `database` into `directory` (safe while it is in use), keep the newest `keep` copies."""
    if not database.is_file():
        raise BackupError(f"{database} not found")
    directory.mkdir(parents=True, exist_ok=True)
    # UTC, so copies made on the host and in the container sort together.
    target = directory / f"{PREFIX}{datetime.now(UTC):%Y%m%d-%H%M%S}Z.db"
    source = sqlite3.connect(database)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
        [result] = copy.execute("PRAGMA integrity_check").fetchone()
    finally:
        copy.close()
        source.close()
    if result != "ok":
        target.unlink()
        raise BackupError(f"Backup of {database} failed the integrity check: {result}")
    for old in sorted(directory.glob(f"{PREFIX}*.db"))[:-keep]:
        old.unlink()
    return target


def dump(database: Path) -> str:
    """A text SQL dump of `database`, consistent even while the app writes to it."""
    if not database.is_file():
        raise BackupError(f"{database} not found")
    source = sqlite3.connect(database)
    copy = sqlite3.connect(":memory:")
    try:
        source.backup(copy)
        return "\n".join(copy.iterdump()) + "\n"
    finally:
        copy.close()
        source.close()


def push_dump(database: Path, file: GitHubFile) -> bool:
    """Commit a dump of `database` as `file`; return False if nothing changed since the last."""
    return file.write(dump(database), f"Backup {datetime.now(UTC):%Y-%m-%d %H:%M}Z")


def backup_file(settings: Settings, repo: str) -> GitHubFile:
    """The dump in the backup repository `repo`, with the token and branch of the settings."""
    return GitHubFile(
        repo,
        DUMP,
        token=settings.backup_github_token.get_secret_value(),
        branch=settings.db_backup_branch,
        api_url=settings.github_api_url,
    )


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Back up the kommunalka database.")
    parser.add_argument("--database", type=Path, default=make_url(settings.database_url).database)
    parser.add_argument("--directory", type=Path, default=settings.backup_dir)
    parser.add_argument("--keep", type=int, default=settings.backup_keep, help="copies to keep")
    parser.add_argument(
        "--every", type=int, default=settings.backup_interval, help="repeat every N seconds"
    )
    parser.add_argument(
        "--repo", default=settings.db_backup_repo_url, help="GitHub repository to push a dump to"
    )
    args = parser.parse_args()
    if args.database is None:
        parser.error(f"no database file in {settings.database_url}")
    while True:
        try:
            print(backup(args.database, args.directory, keep=args.keep), flush=True)
            if args.repo:
                file = backup_file(settings, args.repo)
                state = "pushed" if push_dump(args.database, file) else "unchanged"
                print(f"{file.repo}: {state}", flush=True)
        except (BackupError, GitHubError) as error:
            if args.every is None:
                parser.exit(1, f"error: {error}\n")
            print(f"error: {error}", flush=True)
        if args.every is None:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
