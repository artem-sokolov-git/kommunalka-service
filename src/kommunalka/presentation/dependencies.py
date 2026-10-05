from typing import Annotated

from fastapi import Depends, Request

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork


def get_uow(request: Request) -> UnitOfWork:
    return SqlUnitOfWork(request.app.state.engine)


UowDep = Annotated[UnitOfWork, Depends(get_uow)]
