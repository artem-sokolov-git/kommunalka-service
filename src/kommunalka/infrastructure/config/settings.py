"""Settings from environment variables with the `KS_` prefix or from `.env`."""

from functools import cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KS_",
        env_file=".env",
        extra="ignore",
    )

    # A PostgreSQL on this machine; the Docker stack sets its own URL.
    database_url: str = "postgresql+psycopg://kommunalka:kommunalka@localhost:5432/kommunalka"
    timezone: str = "Europe/Kyiv"

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
