from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from kommunalka.domain.exceptions import DomainError, DuplicateMeterError


@dataclass(frozen=True, slots=True, kw_only=True)
class Meter:
    """Meter of a metered service installed in a household."""

    household_id: UUID
    service_id: UUID
    serial_number: str
    label: str
    installed_on: date
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


def ensure_unique_meter(meter: Meter, existing: Iterable[Meter]) -> None:
    """Raise if another meter has the same serial number or the same label in the household."""
    for other in existing:
        if other.id == meter.id:
            continue
        if other.serial_number == meter.serial_number:
            raise DuplicateMeterError(f"Serial number {meter.serial_number!r} is already taken")
        if other.household_id == meter.household_id and other.label == meter.label:
            raise DuplicateMeterError(f"Label {meter.label!r} is already taken")
