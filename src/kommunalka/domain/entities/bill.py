from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import (
    DomainError,
    DuplicateBillError,
    PeriodAlreadyBilledError,
)
from kommunalka.domain.value_objects import BillLine, DateRange


@dataclass(frozen=True, slots=True, kw_only=True)
class Bill:
    """Household bill for a billing month, at most one line per service."""

    household_id: UUID
    period_start: date
    period_end: date
    lines: tuple[BillLine, ...]
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.period_end < self.period_start:
            raise DomainError("Bill period_end must not be earlier than period_start")
        if self.period != DateRange.month_of(self.period_start):
            raise DomainError("Bill period must be a whole calendar month")
        service_ids = [line.service_id for line in self.lines]
        if len(service_ids) != len(set(service_ids)):
            raise DomainError("Bill must contain at most one line per service")

    @property
    def period(self) -> DateRange:
        return DateRange(self.period_start, self.period_end)

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0.00"))


def ensure_unique_bill(bill: Bill, existing: Iterable[Bill]) -> None:
    """Raise if the household already has another bill for the same month."""
    for other in existing:
        if (
            other.id != bill.id
            and other.household_id == bill.household_id
            and other.period == bill.period
        ):
            raise DuplicateBillError(f"Bill for {bill.period_start:%Y-%m} already exists")


def ensure_not_billed(household_id: UUID, period: DateRange, bills: Iterable[Bill]) -> None:
    """Raise if the household month is already billed, so its readings can't change."""
    for bill in bills:
        if bill.household_id == household_id and bill.period == period:
            raise PeriodAlreadyBilledError(f"{period.start:%Y-%m} is already billed")
