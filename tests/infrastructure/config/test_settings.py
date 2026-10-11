from datetime import datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from kommunalka.infrastructure.config import Settings
from kommunalka.infrastructure.config import settings as settings_module
from kommunalka.presentation import dependencies

ORGANIZATION_ID = UUID("6c1f8a2e-0b5d-4f3a-9e7c-2d4b8a1c5f90")


def test_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///kommunalka.db"
    assert settings.timezone == "Europe/Kyiv"
    assert settings.backup_keep == 30
    assert settings.db_backup_branch == "main"


@pytest.mark.parametrize("name", ["DB_BACKUP_REPO_URL", "BACKUP_GITHUB_TOKEN"])
def test_secrets_have_no_defaults(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(f"KOMMUNALKA_{name}")

    with pytest.raises(ValidationError, match=name.lower()):
        Settings(_env_file=None)


def test_reads_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOMMUNALKA_DATABASE_URL", "sqlite:////data/kommunalka.db")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_GITHUB_TOKEN", "github_pat_secret")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:////data/kommunalka.db"
    assert settings.backup_github_token.get_secret_value() == "github_pat_secret"
    assert "github_pat_secret" not in repr(settings)


def test_reads_env_file_ignoring_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KOMMUNALKA_DB_BACKUP_REPO_URL")
    env = tmp_path / ".env"
    env.write_text("BWS_PROJECT_ID=abc\nKOMMUNALKA_DB_BACKUP_REPO_URL=https://example.test/b.git\n")

    settings = Settings(_env_file=env)

    assert settings.db_backup_repo_url == "https://example.test/b.git"


def test_reads_secrets_from_bitwarden(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def read_secrets(access_token: str, organization_id: UUID) -> dict[str, str]:
        calls.append((access_token, organization_id))
        return {
            "KOMMUNALKA_DB_BACKUP_REPO_URL": "owner/from-bitwarden",
            "KOMMUNALKA_BACKUP_GITHUB_TOKEN": "github_pat_bitwarden",
            "KOMMUNALKA_UNKNOWN": "ignored",
            "OTHER_SERVICE_TOKEN": "ignored",
        }

    monkeypatch.setattr(settings_module, "read_secrets", read_secrets)
    monkeypatch.setenv("BWS_ACCESS_TOKEN", "0.machine.token")
    monkeypatch.setenv("BWS_ORGANIZATION_ID", str(ORGANIZATION_ID))
    monkeypatch.delenv("KOMMUNALKA_DB_BACKUP_REPO_URL")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_GITHUB_TOKEN", "github_pat_environment")

    settings = Settings(_env_file=None)

    assert calls == [("0.machine.token", ORGANIZATION_ID)]
    assert settings.db_backup_repo_url == "owner/from-bitwarden"
    assert settings.backup_github_token.get_secret_value() == "github_pat_environment"


@pytest.mark.parametrize("name", ["BWS_ACCESS_TOKEN", "BWS_ORGANIZATION_ID"])
def test_skips_bitwarden_without_both_access_variables(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings_module, "read_secrets", pytest.fail)
    monkeypatch.setenv("BWS_ACCESS_TOKEN", "0.machine.token")
    monkeypatch.setenv("BWS_ORGANIZATION_ID", str(ORGANIZATION_ID))
    monkeypatch.delenv(name)

    Settings(_env_file=None)


def test_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, timezone="Mars/Olympus")


def test_today_is_taken_in_the_configured_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, timezone="Pacific/Kiritimati")
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    assert dependencies.get_today() == datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
