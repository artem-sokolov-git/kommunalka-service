from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.config import get_settings
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork


def get_uow(request: Request) -> UnitOfWork:
    return SqlUnitOfWork(request.app.state.engine)


UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_today() -> date:
    """The current date in the configured timezone; a dependency, so tests can fix it."""
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


TodayDep = Annotated[date, Depends(get_today)]
