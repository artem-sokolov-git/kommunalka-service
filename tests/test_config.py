from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from kommunalka.config import Settings
from kommunalka.presentation import dependencies


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "DB_BACKUP_REPO_URL", "BACKUP_GITHUB_TOKEN"):
        monkeypatch.delenv(f"KOMMUNALKA_{name}", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///kommunalka.db"
    assert settings.db_backup_repo_url is None
    assert settings.backup_github_token is None


def test_reads_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOMMUNALKA_DATABASE_URL", "sqlite:////data/kommunalka.db")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_GITHUB_TOKEN", "github_pat_secret")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:////data/kommunalka.db"
    assert settings.backup_github_token is not None
    assert settings.backup_github_token.get_secret_value() == "github_pat_secret"
    assert "github_pat_secret" not in repr(settings)


def test_reads_env_file_ignoring_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KOMMUNALKA_DB_BACKUP_REPO_URL", raising=False)
    env = tmp_path / ".env"
    env.write_text("BWS_PROJECT_ID=abc\nKOMMUNALKA_DB_BACKUP_REPO_URL=https://example.test/b.git\n")

    settings = Settings(_env_file=env)

    assert settings.db_backup_repo_url == "https://example.test/b.git"


def test_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, timezone="Mars/Olympus")


def test_today_is_taken_in_the_configured_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, timezone="Pacific/Kiritimati")
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    assert dependencies.get_today() == datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
