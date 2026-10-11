"""Restore the database: python -m kommunalka.presentation.cli.restore
    [--revision REV | --file PATH | --list | --if-missing]

By default the latest dump in `db_backup_repo_url` is downloaded through the GitHub API and
restored into the database of `database_url`. Stop the app before restoring. `--if-missing`
runs on start: it restores only into a missing database and does nothing without a
repository or backups in it.
"""

import argparse
from pathlib import Path

from sqlalchemy import make_url

from kommunalka.infrastructure.backup.backup import BackupError, backup_file
from kommunalka.infrastructure.backup.github import GitHubError
from kommunalka.infrastructure.backup.restore import (
    fetch_dump,
    list_backups,
    restore_copy,
    restore_dump,
)
from kommunalka.infrastructure.config import get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Restore the kommunalka database.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--revision", default="", help="commit to restore (default: latest)")
    source.add_argument("--file", type=Path, help="a local copy (.db) or dump (.sql) instead")
    source.add_argument("--list", action="store_true", help="list backups in the repository")
    source.add_argument(
        "--if-missing",
        action="store_true",
        help="restore the latest backup only when there is no database yet (on start)",
    )
    parser.add_argument("--database", type=Path, default=make_url(settings.database_url).database)
    parser.add_argument("--repo", default=settings.db_backup_repo_url)
    args = parser.parse_args()
    if args.database is None:
        parser.error(f"no database file in {settings.database_url}")
    if args.if_missing and (args.database.exists() or not args.repo):
        return
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
            if args.if_missing:
                dump = file.read()
                if dump is None:
                    print(f"no backups in {file.repo} yet, starting with a new database")
                    return
            else:
                dump = fetch_dump(file, args.revision or None)
            origin = f"{file.repo} at {args.revision or file.branch}"
            previous = restore_dump(dump, args.database)
    except (BackupError, GitHubError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"restored {args.database} from {origin}")
    if previous is not None:
        print(f"the previous database is kept in {previous}")


if __name__ == "__main__":
    main()
