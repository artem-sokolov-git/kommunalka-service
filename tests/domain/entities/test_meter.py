from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from kommunalka.domain import (
    DateRange,
    DomainError,
    DuplicateMeterError,
    Meter,
    Reading,
    ensure_unique_meter,
)

HOUSEHOLD_ID = uuid4()


def make_meter(
    serial_number: str = "SN-1", label: str = "Kitchen", household_id: UUID = HOUSEHOLD_ID
) -> Meter:
    return Meter(
        household_id=household_id,
        service_id=uuid4(),
        serial_number=serial_number,
        label=label,
        installed_on=date(2025, 1, 1),
    )


@pytest.mark.parametrize(("serial_number", "label"), [(" ", "Kitchen"), ("SN-1", " ")])
def test_rejects_empty_fields(serial_number: str, label: str) -> None:
    with pytest.raises(DomainError):
        make_meter(serial_number, label)


def test_rejects_removal_before_installation() -> None:
    with pytest.raises(DomainError):
        Meter(
            household_id=HOUSEHOLD_ID,
            service_id=uuid4(),
            serial_number="SN-1",
            label="Kitchen",
            installed_on=date(2025, 1, 1),
            removed_on=date(2024, 12, 31),
        )


def test_is_active_until_removed() -> None:
    meter = make_meter()

    assert meter.is_active
    assert not Meter(
        household_id=meter.household_id,
        service_id=meter.service_id,
        serial_number=meter.serial_number,
        label=meter.label,
        installed_on=meter.installed_on,
        removed_on=date(2026, 1, 1),
    ).is_active


def test_ignores_itself() -> None:
    meter = make_meter()

    ensure_unique_meter(meter, [meter])


def test_serial_number_is_unique_globally() -> None:
    existing = make_meter("SN-1", "Kitchen")

    with pytest.raises(DuplicateMeterError):
        ensure_unique_meter(make_meter("SN-1", "Hall", household_id=uuid4()), [existing])


def test_label_is_unique_within_household() -> None:
    existing = make_meter("SN-1", "Kitchen")

    with pytest.raises(DuplicateMeterError):
        ensure_unique_meter(make_meter("SN-2", "Kitchen"), [existing])
    ensure_unique_meter(make_meter("SN-2", "Kitchen", household_id=uuid4()), [existing])


def test_is_in_service_between_installation_and_removal() -> None:
    meter = Meter(
        household_id=HOUSEHOLD_ID,
        service_id=uuid4(),
        serial_number="SN-1",
        label="Kitchen",
        installed_on=date(2025, 1, 15),
        removed_on=date(2026, 10, 15),
    )

    assert not meter.is_in_service_on(date(2025, 1, 14))
    assert meter.is_in_service_on(date(2026, 10, 15))
    assert not meter.is_in_service_on(date(2026, 10, 16))
    assert meter.is_in_service_during(DateRange.month_of(date(2025, 1, 1)))
    assert not meter.is_in_service_during(DateRange.month_of(date(2026, 11, 1)))


def test_remove() -> None:
    meter = make_meter()
    reading = Reading(meter_id=meter.id, value=Decimal(1), taken_on=date(2026, 10, 2))

    removed = meter.remove(date(2026, 10, 15), [reading])

    assert removed.removed_on == date(2026, 10, 15)
    with pytest.raises(DomainError):
        removed.remove(date(2026, 10, 16), [])
    with pytest.raises(DomainError):
        meter.remove(date(2026, 10, 1), [reading])
