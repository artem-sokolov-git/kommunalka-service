"""Settings from environment variables with the `KS_` prefix or from `.env`."""

from functools import cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KS_",
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    # A PostgreSQL on this machine; the Docker stack sets its own URL.
    database_url: str = "postgresql+psycopg://kommunalka:kommunalka@localhost:5432/kommunalka"
    timezone: str = "Europe/Kyiv"
    # The Telegram bot runs only with a token and users: it answers the ids listed (`1,2`).
    bot_token: str = ""
    allowed_users_tg_ids: Annotated[list[int], NoDecode] = []

    @field_validator("allowed_users_tg_ids", mode="before")
    @classmethod
    def _split_user_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [part for part in value.replace(" ", "").split(",") if part]
        return value

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
