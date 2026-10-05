"""Online backup of the SQLite database with rotation.

Usage: python -m kommunalka.infrastructure.db.backup DATABASE DIRECTORY [--keep N] [--every SECONDS]
"""

import argparse
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

PREFIX = "kommunalka-"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the kommunalka database.")
    parser.add_argument("database", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--keep", type=int, default=30, help="copies to keep")
    parser.add_argument("--every", type=int, help="repeat every N seconds")
    args = parser.parse_args()
    while True:
        try:
            print(backup(args.database, args.directory, keep=args.keep), flush=True)
        except BackupError as error:
            if args.every is None:
                parser.exit(1, f"error: {error}\n")
            print(f"error: {error}", flush=True)
        if args.every is None:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
