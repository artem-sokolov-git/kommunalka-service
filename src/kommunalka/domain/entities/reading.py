from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import DomainError, DuplicateReadingError
from kommunalka.domain.value_objects import DateRange

if TYPE_CHECKING:
    from kommunalka.domain.entities.meter import Meter


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


def next_reading(
    meter: "Meter", last: Reading | None, *, value: Decimal, taken_on: date, today: date
) -> Reading:
    """Create a reading that follows `last`, the latest reading of the meter."""
    if taken_on > today:
        raise DomainError(f"Reading date {taken_on} is in the future")
    if not meter.is_in_service_on(taken_on):
        raise DomainError(f"Meter {meter.label!r} is not in service on {taken_on}")
    if last is not None and taken_on <= last.taken_on:
        raise DomainError(f"Reading must be taken after the last one on {last.taken_on}")
    reading = Reading(
        meter_id=meter.id,
        value=value,
        taken_on=taken_on,
        previous_taken_on=None if last is None else last.taken_on,
    )
    if last is not None:
        reading.consumption_since(last)
    return reading


def readings_for_month(
    readings: Iterable[Reading], period: DateRange
) -> tuple[Reading | None, Reading | None]:
    """Return the previous reading and the one closing `period`, among readings of one meter."""
    readings = list(readings)
    current = next((r for r in readings if r.billing_period == period), None)
    if current is None:
        return None, None
    previous = next((r for r in readings if r.taken_on == current.previous_taken_on), None)
    return previous, current


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
