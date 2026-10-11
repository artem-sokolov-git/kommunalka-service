from collections.abc import Iterator
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from kommunalka.infrastructure.db.engine import create_db_engine
from kommunalka.presentation.app import create_app
from kommunalka.presentation.dependencies import get_today

ROOT = Path(__file__).parents[1]


@pytest.fixture(autouse=True)
def _settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required secrets in the environment and no Bitwarden, even with a token in the shell."""
    monkeypatch.delenv("BWS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("BWS_ORGANIZATION_ID", raising=False)
    monkeypatch.setenv("KOMMUNALKA_DB_BACKUP_REPO_URL", "owner/backups")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_GITHUB_TOKEN", "github_pat_environment")


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    config = Config(
        ROOT / "alembic.ini",
        toml_file=ROOT / "pyproject.toml",
        stdout=StringIO(),
        attributes={"configure_logger": False},
    )
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'test.db'}")
    return config


@pytest.fixture
def engine(alembic_config: Config) -> Iterator[Engine]:
    """Engine of a fresh database migrated to head."""
    command.upgrade(alembic_config, "head")
    engine = create_db_engine(alembic_config.get_main_option("sqlalchemy.url") or "")
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """App client where today is 2026-12-31, after every date the tests use."""
    app = create_app(engine)
    app.dependency_overrides[get_today] = lambda: date(2026, 12, 31)
    with TestClient(app) as client:
        yield client
