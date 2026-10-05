from fastapi import status

from kommunalka.application.exceptions import ConflictError, NotFoundError
from kommunalka.domain import (
    DomainError,
    DuplicateBillError,
    DuplicateHouseholdError,
    DuplicateMeterError,
    DuplicateReadingError,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
)

HANDLED_ERRORS = (NotFoundError, ConflictError, DomainError)

CONFLICTS = (
    DuplicateBillError,
    DuplicateHouseholdError,
    DuplicateMeterError,
    DuplicateReadingError,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
)


def describe_error(exc: Exception) -> tuple[int, str]:
    """HTTP status and message for an application or domain error."""
    if isinstance(exc, NotFoundError):
        return status.HTTP_404_NOT_FOUND, str(exc)
    if isinstance(exc, (ConflictError, *CONFLICTS)):
        return status.HTTP_409_CONFLICT, str(exc)
    return status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
