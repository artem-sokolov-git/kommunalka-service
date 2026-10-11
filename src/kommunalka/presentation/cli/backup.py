"""Back up the database: python -m kommunalka.presentation.cli.backup [--every SECONDS] [...]

Everything comes from the settings: the database of `database_url`, copies in `backup_dir`.
With `db_backup_repo_url`, a text dump of the database is also pushed to that GitHub
repository. Options override the settings for one run.
"""

import argparse
import time
from pathlib import Path

from sqlalchemy import make_url

from kommunalka.infrastructure.backup.backup import BackupError, backup, backup_file, push_dump
from kommunalka.infrastructure.backup.github import GitHubError
from kommunalka.infrastructure.config import get_settings


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
