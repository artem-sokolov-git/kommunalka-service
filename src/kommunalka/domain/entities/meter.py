from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date
from uuid import UUID, uuid4

from kommunalka.domain.entities.reading import Reading
from kommunalka.domain.exceptions import DomainError, DuplicateMeterError
from kommunalka.domain.value_objects import DateRange


@dataclass(frozen=True, slots=True, kw_only=True)
class Meter:
    """Meter of a metered service installed in a household."""

    household_id: UUID
    service_id: UUID
    serial_number: str
    label: str
    installed_on: date
    model: str | None = None
    removed_on: date | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.serial_number.strip():
            raise DomainError("Meter serial number must not be empty")
        if not self.label.strip():
            raise DomainError("Meter label must not be empty")
        if self.removed_on is not None and self.removed_on < self.installed_on:
            raise DomainError("Meter removed_on must not be earlier than installed_on")

    @property
    def is_active(self) -> bool:
        return self.removed_on is None

    def is_in_service_on(self, day: date) -> bool:
        return self.installed_on <= day and (self.removed_on is None or day <= self.removed_on)

    def is_in_service_during(self, period: DateRange) -> bool:
        return self.installed_on <= period.end and (
            self.removed_on is None or self.removed_on >= period.start
        )

    def remove(self, removed_on: date, readings: Iterable[Reading]) -> "Meter":
        """Return the meter removed on `removed_on`; none of its readings may be later."""
        if not self.is_active:
            raise DomainError(f"Meter {self.label!r} is already removed")
        if any(reading.taken_on > removed_on for reading in readings):
            raise DomainError(f"Meter {self.label!r} has readings after {removed_on}")
        return replace(self, removed_on=removed_on)


def ensure_unique_meter(meter: Meter, existing: Iterable[Meter]) -> None:
    """Raise if another meter has the same serial number or the same label in the household."""
    for other in existing:
        if other.id == meter.id:
            continue
        if other.serial_number == meter.serial_number:
            raise DuplicateMeterError(f"Serial number {meter.serial_number!r} is already taken")
        if other.household_id == meter.household_id and other.label == meter.label:
            raise DuplicateMeterError(f"Label {meter.label!r} is already taken")
