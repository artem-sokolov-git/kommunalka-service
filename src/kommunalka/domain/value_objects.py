import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from uuid import UUID

from kommunalka.domain.exceptions import DomainError

KOPECK = Decimal("0.01")


class Unit(StrEnum):
    """Unit of measurement of a metered service."""

    KWH = "kWh"
    CUBIC_METER = "m3"


@dataclass(frozen=True, slots=True)
class DateRange:
    """Date range with both bounds inclusive."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise DomainError("DateRange end must not be earlier than start")

    @classmethod
    def month_of(cls, day: date) -> "DateRange":
        """Return the whole calendar month containing `day`."""
        last = calendar.monthrange(day.year, day.month)[1]
        return cls(day.replace(day=1), day.replace(day=last))

    @classmethod
    def month_before(cls, day: date) -> "DateRange":
        """Return the whole calendar month preceding the month of `day`."""
        return cls.month_of(day.replace(day=1) - timedelta(days=1))

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True, slots=True, kw_only=True)
class MeteredBillLine:
    """Charge calculated from consumption and tariff price."""

    service_id: UUID
    quantity: Decimal
    price: Decimal

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise DomainError("Bill line quantity must not be negative")
        if self.price < 0:
            raise DomainError("Bill line price must not be negative")

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.price).quantize(KOPECK, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True, kw_only=True)
class FixedBillLine:
    """Charge with a ready amount, e.g. gas transportation."""

    service_id: UUID
    amount: Decimal

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise DomainError("Bill line amount must not be negative")


type BillLine = MeteredBillLine | FixedBillLine
