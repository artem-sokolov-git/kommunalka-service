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


def test_reads_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOMMUNALKA_DATABASE_URL", "sqlite:////data/kommunalka.db")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:////data/kommunalka.db"


def test_reads_env_file_ignoring_other_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("BWS_PROJECT_ID=abc\nKOMMUNALKA_TIMEZONE=Europe/Warsaw\n")

    settings = Settings(_env_file=env)

    assert settings.timezone == "Europe/Warsaw"


def test_reads_settings_from_bitwarden(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def read_secrets(access_token: str, organization_id: UUID) -> dict[str, str]:
        calls.append((access_token, organization_id))
        return {
            "KOMMUNALKA_DATABASE_URL": "sqlite:///from-bitwarden.db",
            "KOMMUNALKA_TIMEZONE": "Europe/Warsaw",
            "KOMMUNALKA_UNKNOWN": "ignored",
            "OTHER_SERVICE_TOKEN": "ignored",
        }

    monkeypatch.setattr(settings_module, "read_secrets", read_secrets)
    monkeypatch.setenv("BWS_ACCESS_TOKEN", "0.machine.token")
    monkeypatch.setenv("BWS_ORGANIZATION_ID", str(ORGANIZATION_ID))
    monkeypatch.setenv("KOMMUNALKA_TIMEZONE", "Europe/Kyiv")

    settings = Settings(_env_file=None)

    assert calls == [("0.machine.token", ORGANIZATION_ID)]
    assert settings.database_url == "sqlite:///from-bitwarden.db"
    assert settings.timezone == "Europe/Kyiv"


def test_reads_bitwarden_access_from_secret_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def read_secrets(access_token: str, organization_id: UUID) -> dict[str, str]:
        calls.append((access_token, organization_id))
        return {}

    (tmp_path / "bws_access_token").write_text("0.machine.token\n")
    (tmp_path / "bws_organization_id").write_text(f"{ORGANIZATION_ID}\n")
    monkeypatch.setattr(settings_module, "read_secrets", read_secrets)

    Settings(_env_file=None, _secrets_dir=tmp_path)

    assert calls == [("0.machine.token", ORGANIZATION_ID)]


def test_skips_bitwarden_with_empty_secret_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bws_access_token").write_text("")
    (tmp_path / "bws_organization_id").write_text("\n")
    monkeypatch.setattr(settings_module, "read_secrets", pytest.fail)

    Settings(_env_file=None, _secrets_dir=tmp_path)


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
