import pytest
from sqlalchemy import Engine

from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork


@pytest.fixture
def uow(engine: Engine) -> SqlUnitOfWork:
    return SqlUnitOfWork(engine)
