from collections.abc import Iterator
from datetime import date
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.postgres import PostgresContainer

from kommunalka.infrastructure.db.engine import create_db_engine
from kommunalka.presentation.app import create_app
from kommunalka.presentation.dependencies import get_today

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresContainer]:
    """One PostgreSQL server for the whole run; every test gets its own database in it."""
    with PostgresContainer("postgres:18.6", driver="psycopg") as container:
        yield container


@pytest.fixture
def database_url(postgres: PostgresContainer) -> Iterator[str]:
    """URL of an empty database that is dropped after the test."""
    name = f"test_{uuid4().hex}"
    server = create_engine(postgres.get_connection_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    yield postgres.get_connection_url().rsplit("/", 1)[0] + f"/{name}"
    with server.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    server.dispose()


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(
        ROOT / "alembic.ini",
        toml_file=ROOT / "pyproject.toml",
        stdout=StringIO(),
        attributes={"configure_logger": False},
    )
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture
def engine(alembic_config: Config, database_url: str) -> Iterator[Engine]:
    """Engine of a fresh database migrated to head."""
    command.upgrade(alembic_config, "head")
    engine = create_db_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """App client where today is 2026-12-31, after every date the tests use."""
    app = create_app(engine)
    app.dependency_overrides[get_today] = lambda: date(2026, 12, 31)
    with TestClient(app) as client:
        yield client
