"""Settings from environment variables with the `KOMMUNALKA_` prefix or from `.env`."""

from functools import cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KOMMUNALKA_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "sqlite:///kommunalka.db"
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
