from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import DomainError, OverlappingTariffPeriodError
from kommunalka.domain.value_objects import DateRange


@dataclass(frozen=True, slots=True, kw_only=True)
class TariffPeriod:
    """Price per unit of a metered service."""

    service_id: UUID
    price: Decimal
    valid_from: date
    valid_to: date
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.price < 0:
            raise DomainError("Tariff price must not be negative")
        if self.valid_to < self.valid_from:
            raise DomainError("Tariff period valid_to must not be earlier than valid_from")

    @property
    def period(self) -> DateRange:
        return DateRange(self.valid_from, self.valid_to)

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
