from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from kommunalka.application.exceptions import NotFoundError
from kommunalka.domain import (
    DomainError,
    DuplicateBillError,
    DuplicateHouseholdError,
    DuplicateMeterError,
    DuplicateReadingError,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
)

CONFLICTS = (
    DuplicateBillError,
    DuplicateHouseholdError,
    DuplicateMeterError,
    DuplicateReadingError,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _handler(status.HTTP_404_NOT_FOUND))
    app.add_exception_handler(DomainError, _domain_error)
    # Unique constraints catch duplicates that slipped past the checks in a race.
    app.add_exception_handler(IntegrityError, _handler(status.HTTP_409_CONFLICT, "Conflict"))


async def _domain_error(_request: Request, exc: Exception) -> JSONResponse:
    code = (
        status.HTTP_409_CONFLICT
        if isinstance(exc, CONFLICTS)
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return JSONResponse({"detail": str(exc)}, status_code=code)


def _handler(
    code: int, detail: str | None = None
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": detail or str(exc)}, status_code=code)

    return handle
