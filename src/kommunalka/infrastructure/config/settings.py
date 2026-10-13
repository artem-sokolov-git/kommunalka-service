"""Settings from environment variables with the `KOMMUNALKA_` prefix or from `.env`.

With `BWS_ACCESS_TOKEN` and `BWS_ORGANIZATION_ID` there, they are also read from
Bitwarden Secrets Manager as secrets `KOMMUNALKA_<SETTING>`, below them in priority.
The two can be files named `bws_access_token` and `bws_organization_id` in `secrets/`
(locally) or `/run/secrets/` (Docker secrets).
"""

from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from kommunalka.infrastructure.config.bitwarden import read_secrets

ENV_PREFIX = "KOMMUNALKA_"
SECRETS_DIRS = (Path("secrets"), Path("/run/secrets"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        extra="ignore",
        secrets_dir=[directory for directory in SECRETS_DIRS if directory.is_dir()],
    )

    database_url: str = "sqlite:///kommunalka.db"
    timezone: str = "Europe/Kyiv"

    bws_access_token: SecretStr | None = Field(default=None, validation_alias="BWS_ACCESS_TOKEN")
    bws_organization_id: UUID | None = Field(default=None, validation_alias="BWS_ORGANIZATION_ID")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            BitwardenSettingsSource(settings_cls),
        )

    @field_validator("bws_access_token", "bws_organization_id", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        """An empty secret file (`make install` creates them so) means no Bitwarden."""
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(f"unknown timezone {value!r}") from None
        return value


class BitwardenSettingsSource(PydanticBaseSettingsSource):
    """Secrets named like the environment variables (`KOMMUNALKA_DATABASE_URL`).

    Read only with both `BWS_ACCESS_TOKEN` and `BWS_ORGANIZATION_ID` set.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        token = self.current_state.get("BWS_ACCESS_TOKEN")
        organization_id = self.current_state.get("BWS_ORGANIZATION_ID")
        if not token or not organization_id:
            return {}
        values = {}
        for key, value in read_secrets(str(token), UUID(str(organization_id))).items():
            name = key.removeprefix(ENV_PREFIX).lower()
            if key.startswith(ENV_PREFIX) and name in self.settings_cls.model_fields:
                values[name] = value
        return values


@cache
def get_settings() -> Settings:
    return Settings()
