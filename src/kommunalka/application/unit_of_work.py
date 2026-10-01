from types import TracebackType
from typing import Protocol, Self

from kommunalka.application.repositories import (
    BillRepository,
    HouseholdRepository,
    MeterRepository,
    ReadingRepository,
    ServiceRepository,
    TariffPeriodRepository,
)


class UnitOfWork(Protocol):
    """Transaction over all repositories; leaving the block without commit rolls back."""

    @property
    def households(self) -> HouseholdRepository: ...
    @property
    def services(self) -> ServiceRepository: ...
    @property
    def meters(self) -> MeterRepository: ...
    @property
    def readings(self) -> ReadingRepository: ...
    @property
    def tariff_periods(self) -> TariffPeriodRepository: ...
    @property
    def bills(self) -> BillRepository: ...

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
