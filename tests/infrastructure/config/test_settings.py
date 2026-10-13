from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from kommunalka.infrastructure.config import Settings
from kommunalka.presentation import dependencies


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
    env.write_text("OTHER_KEY=abc\nKOMMUNALKA_TIMEZONE=Europe/Warsaw\n")

    settings = Settings(_env_file=env)

    assert settings.timezone == "Europe/Warsaw"


def test_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, timezone="Mars/Olympus")


def test_today_is_taken_in_the_configured_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, timezone="Pacific/Kiritimati")
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    assert dependencies.get_today() == datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
