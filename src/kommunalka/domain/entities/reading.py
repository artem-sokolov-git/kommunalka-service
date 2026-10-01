from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import DomainError, DuplicateReadingError
from kommunalka.domain.value_objects import DateRange


@dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """Meter reading. `previous_taken_on` is None for the first reading of a meter.

    A reading closes the month before the one it is taken in.
    """

    meter_id: UUID
    value: Decimal
    taken_on: date
    previous_taken_on: date | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.value < 0:
            raise DomainError("Reading value must not be negative")
        if self.previous_taken_on is not None and self.previous_taken_on >= self.taken_on:
            raise DomainError("Previous reading must be taken earlier")

    @property
    def period(self) -> DateRange | None:
        if self.previous_taken_on is None:
            return None
        return DateRange(self.previous_taken_on, self.taken_on)

    @property
    def billing_period(self) -> DateRange:
        return DateRange.month_before(self.taken_on)

    def consumption_since(self, previous: "Reading") -> Decimal:
        """Return consumption since `previous`, which must be the preceding reading."""
        if previous.meter_id != self.meter_id:
            raise DomainError("Readings belong to different meters")
        if previous.taken_on != self.previous_taken_on:
            raise DomainError("Reading is not the previous one for this reading")
        if previous.value > self.value:
            raise DomainError("Reading value decreased")
        return self.value - previous.value


def ensure_unique_reading(reading: Reading, existing: Iterable[Reading]) -> None:
    """Raise if the meter already has another reading for the same billing month."""
    for other in existing:
        if (
            other.id != reading.id
            and other.meter_id == reading.meter_id
            and other.billing_period == reading.billing_period
        ):
            raise DuplicateReadingError(
                f"Reading for {reading.billing_period.start:%Y-%m} already exists"
            )
