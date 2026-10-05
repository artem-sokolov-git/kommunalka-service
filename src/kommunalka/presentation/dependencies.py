from datetime import date
from typing import Annotated

from fastapi import Depends, Request

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork


def get_uow(request: Request) -> UnitOfWork:
    return SqlUnitOfWork(request.app.state.engine)


UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_today() -> date:
    """The current date; a dependency, so tests can fix it."""
    return date.today()


TodayDep = Annotated[date, Depends(get_today)]
