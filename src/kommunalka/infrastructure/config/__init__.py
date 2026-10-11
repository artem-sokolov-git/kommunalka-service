"""Settings of the service, from the environment, `.env` or Bitwarden Secrets Manager."""

from kommunalka.infrastructure.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
