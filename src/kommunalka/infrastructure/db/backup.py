"""Online backup of the SQLite database with rotation, optionally pushed to a git repository.

Usage: python -m kommunalka.infrastructure.db.backup [--every SECONDS] [...]

Everything comes from the settings (`kommunalka.config`): the database of `database_url`,
copies in `backup_dir`. With `db_backup_repo_url`, a text dump of the database is also
committed to a clone of that repository and pushed; the git history is the history of
backups. Options override the settings for one run.
"""

import argparse
import base64
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import make_url

from kommunalka.config import get_settings

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


def push_dump(
    database: Path, clone: Path, remote: str, *, token: str | None = None, branch: str = "main"
) -> bool:
    """Commit a text dump of `database` to `clone` of `remote` and push it.

    Return True if the dump changed since the last backup.
    """
    if not database.is_file():
        raise BackupError(f"{database} not found")
    if not (clone / ".git").is_dir():
        _git(None, token, "clone", remote, str(clone))
    source = sqlite3.connect(database)
    copy = sqlite3.connect(":memory:")
    try:
        source.backup(copy)  # a consistent snapshot, even while the app writes
        (clone / DUMP).write_text("\n".join(copy.iterdump()) + "\n")
    finally:
        copy.close()
        source.close()
    _git(clone, token, "add", DUMP)
    changed = _git(clone, token, "diff", "--cached", "--quiet", check=False).returncode != 0
    if changed:
        _git(clone, token, "commit", "--quiet", "-m", f"Backup {datetime.now(UTC):%Y-%m-%d %H:%M}Z")
    # Pushed every time, so a commit left by a failed push goes out with the next run.
    _git(clone, token, "push", "--quiet", "origin", f"HEAD:{branch}")
    return changed


def _git(
    clone: Path | None, token: str | None, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    options = [
        # The clone may belong to another user than the container's one.
        "-c", "safe.directory=*",
        "-c", "user.name=kommunalka",
        "-c", "user.email=kommunalka@localhost",
    ]  # fmt: skip
    if token:
        credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        options += ["-c", f"http.extraHeader=Authorization: Basic {credentials}"]
    if clone is not None:
        options += ["-C", str(clone)]
    result = subprocess.run(["git", *options, *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise BackupError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


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
        "--git-remote", default=settings.db_backup_repo_url, help="repository to push a dump to"
    )
    parser.add_argument("--git-dir", type=Path, default=settings.db_backup_repo_dir)
    args = parser.parse_args()
    if args.database is None:
        parser.error(f"no database file in {settings.database_url}")
    secret = settings.backup_github_token
    token = secret.get_secret_value() if secret else None
    while True:
        try:
            print(backup(args.database, args.directory, keep=args.keep), flush=True)
            if args.git_remote:
                changed = push_dump(
                    args.database,
                    args.git_dir,
                    args.git_remote,
                    token=token,
                    branch=settings.db_backup_branch,
                )
                state = "pushed" if changed else "unchanged, pushed nothing new"
                print(f"{args.git_remote}: {state}", flush=True)
        except BackupError as error:
            if args.every is None:
                parser.exit(1, f"error: {error}\n")
            print(f"error: {error}", flush=True)
        if args.every is None:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
