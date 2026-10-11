"""Online backup of the SQLite database with rotation, optionally pushed to GitHub.

A text dump of the database can be committed to a GitHub repository through its API; the
history of the file is the history of backups.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from kommunalka.infrastructure.backup.github import GitHubFile
from kommunalka.infrastructure.config import Settings

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
