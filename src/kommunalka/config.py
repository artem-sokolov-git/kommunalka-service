"""Settings from environment variables with the `KOMMUNALKA_` prefix or from `.env`.

With `BWS_ACCESS_TOKEN` and `BWS_ORGANIZATION_ID` there, they are also read from
Bitwarden Secrets Manager as secrets `KOMMUNALKA_<SETTING>`, below them in priority.
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

from kommunalka.infrastructure.bitwarden import read_secrets

ENV_PREFIX = "KOMMUNALKA_"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, env_file=".env", extra="ignore")

    database_url: str = "sqlite:///kommunalka.db"
    timezone: str = "Europe/Kyiv"

    backup_dir: Path = Path("data/backups")
    backup_keep: int = 30
    backup_interval: int | None = None

    db_backup_repo_url: str
    db_backup_branch: str = "main"
    backup_github_token: SecretStr
    github_api_url: str = "https://api.github.com"

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

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(f"unknown timezone {value!r}") from None
        return value


class BitwardenSettingsSource(PydanticBaseSettingsSource):
    """Secrets named like the environment variables (`KOMMUNALKA_BACKUP_GITHUB_TOKEN`).

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
