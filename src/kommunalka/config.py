"""Settings from environment variables with the `KOMMUNALKA_` prefix or from `.env`."""

from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KOMMUNALKA_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///kommunalka.db"
    timezone: str = "Europe/Kyiv"

    backup_dir: Path = Path("data/backups")
    backup_keep: int = 30
    backup_interval: int | None = None

    db_backup_repo_url: str | None = None
    db_backup_branch: str = "main"
    backup_github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(f"unknown timezone {value!r}") from None
        return value


@cache
def get_settings() -> Settings:
    return Settings()
