from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from kommunalka.domain.entities.bill import Bill
from kommunalka.domain.exceptions import (
    DomainError,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
)
from kommunalka.domain.value_objects import DateRange


@dataclass(frozen=True, slots=True, kw_only=True)
class TariffPeriod:
    """Service price: per unit for metered services, per month for unmetered ones.

    The period is open-ended if `valid_to` is None.
    """

    service_id: UUID
    price: Decimal
    valid_from: date
    valid_to: date | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.price < 0:
            raise DomainError("Tariff price must not be negative")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise DomainError("Tariff period valid_to must not be earlier than valid_from")

    @property
    def period(self) -> DateRange:
        return DateRange(self.valid_from, self.valid_to or date.max)

    def covers(self, billing_period: DateRange) -> bool:
        """Return True if the tariff is valid for the whole billing period."""
        return self.period.contains(billing_period.start) and self.period.contains(
            billing_period.end
        )


def ensure_no_overlap(tariff_period: TariffPeriod, existing: Iterable[TariffPeriod]) -> None:
    """Raise if another period of the same service overlaps with the given one."""
    for other in existing:
        if other.id == tariff_period.id or other.service_id != tariff_period.service_id:
            continue
        if tariff_period.period.overlaps(other.period):
            raise OverlappingTariffPeriodError(
                f"Tariff period {tariff_period.valid_from}..{tariff_period.valid_to} "
                f"overlaps with {other.valid_from}..{other.valid_to}"
            )


def next_tariff_period(
    periods: Iterable[TariffPeriod], *, service_id: UUID, price: Decimal, valid_from: date
) -> tuple[TariffPeriod | None, TariffPeriod]:
    """Start a new open-ended price of the service on the first day of a month.

    Return the latest period, closed the day before, if it had to be closed, and the new one.
    """
    if valid_from.day != 1:
        raise DomainError(f"A price changes on the first day of a month, not on {valid_from}")
    own = [period for period in periods if period.service_id == service_id]
    latest = max(own, key=lambda period: period.valid_from) if own else None
    if latest is not None and valid_from <= latest.valid_from:
        raise DomainError(f"A new price must start after {latest.valid_from}")
    new = TariffPeriod(service_id=service_id, price=price, valid_from=valid_from)
    if latest is None or (latest.valid_to is not None and latest.valid_to < valid_from):
        return None, new
    return replace(latest, valid_to=valid_from - timedelta(days=1)), new


def revert_price_change(
    periods: Iterable[TariffPeriod], *, service_id: UUID
) -> tuple[TariffPeriod, TariffPeriod | None]:
    """Undo the latest price of the service.

    Return the latest period, to be removed, and the one before it, open-ended again, if it
    ended right before the latest one.
    """
    own = sorted(
        (period for period in periods if period.service_id == service_id),
        key=lambda period: period.valid_from,
    )
    if not own:
        raise DomainError("Service has no price to undo")
    latest = own[-1]
    previous = own[-2] if len(own) > 1 else None
    if previous is None or previous.valid_to != latest.valid_from - timedelta(days=1):
        return latest, None
    return latest, replace(previous, valid_to=None)


def ensure_price_not_billed(service_id: UUID, valid_from: date, bills: Iterable[Bill]) -> None:
    """Raise if a bill with the service already covers a month from `valid_from` on."""
    for bill in bills:
        if bill.period_end >= valid_from and any(
            line.service_id == service_id for line in bill.lines
        ):
            raise PeriodAlreadyBilledError(
                f"Bill for {bill.period_start:%Y-%m} already uses the current price"
            )
