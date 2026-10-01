from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from kommunalka.infrastructure.db.engine import create_db_engine
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork

ROOT = Path(__file__).parents[2]


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
    command.upgrade(alembic_config, "head")
    engine = create_db_engine(alembic_config.get_main_option("sqlalchemy.url") or "")
    yield engine
    engine.dispose()


@pytest.fixture
def uow(engine: Engine) -> SqlUnitOfWork:
    return SqlUnitOfWork(engine)
