from datetime import date
from decimal import Decimal

import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import (
    correct_reading,
    issue_bill,
    remove_meter,
    submit_reading,
)
from kommunalka.domain import (
    DomainError,
    DuplicateReadingError,
    Household,
    Meter,
    PeriodAlreadyBilledError,
    Reading,
)


def submit(uow: UnitOfWork, meter: Meter, value: str, taken_on: date) -> Reading:
    return submit_reading(uow, meter_id=meter.id, value=Decimal(value), taken_on=taken_on)


def test_links_reading_to_previous(uow: UnitOfWork, gas_meter: Meter) -> None:
    first = submit(uow, gas_meter, "100", date(2026, 9, 2))
    second = submit(uow, gas_meter, "142.5", date(2026, 10, 3))

    assert first.previous_taken_on is None
    assert second.previous_taken_on == first.taken_on
    assert uow.readings.list_by_meter(gas_meter.id) == [first, second]


def test_rejects_reading_not_after_last(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit(uow, gas_meter, "100", date(2026, 10, 3))

    with pytest.raises(DomainError):
        submit(uow, gas_meter, "90", date(2026, 9, 2))


def test_rejects_decreased_value(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit(uow, gas_meter, "100", date(2026, 9, 2))

    with pytest.raises(DomainError):
        submit(uow, gas_meter, "99", date(2026, 10, 3))


def test_rejects_second_reading_in_month(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit(uow, gas_meter, "100", date(2026, 10, 2))

    with pytest.raises(DuplicateReadingError):
        submit(uow, gas_meter, "101", date(2026, 10, 4))


@pytest.mark.parametrize("taken_on", [date(2024, 12, 31), date(2026, 10, 16)])
def test_rejects_reading_out_of_service(uow: UnitOfWork, gas_meter: Meter, taken_on: date) -> None:
    remove_meter(uow, meter_id=gas_meter.id, removed_on=date(2026, 10, 15))

    with pytest.raises(DomainError):
        submit(uow, gas_meter, "1", taken_on)


def test_corrects_reading(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit(uow, gas_meter, "100", date(2026, 9, 2))
    second = submit(uow, gas_meter, "142.5", date(2026, 10, 3))

    corrected = correct_reading(uow, reading_id=second.id, value=Decimal("141"))

    assert uow.readings.get(second.id) == corrected
    assert corrected.value == Decimal("141")


def test_correction_keeps_neighbours_consistent(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit(uow, gas_meter, "100", date(2026, 9, 2))
    middle = submit(uow, gas_meter, "120", date(2026, 10, 3))
    submit(uow, gas_meter, "140", date(2026, 11, 2))

    for value in ("99", "141"):
        with pytest.raises(DomainError):
            correct_reading(uow, reading_id=middle.id, value=Decimal(value))
    assert uow.readings.get(middle.id) == middle


@pytest.mark.usefixtures("gas_tariff")
def test_billed_month_is_frozen(uow: UnitOfWork, household: Household, gas_meter: Meter) -> None:
    submit(uow, gas_meter, "100", date(2026, 9, 2))
    september = submit(uow, gas_meter, "142.5", date(2026, 10, 3))
    issue_bill(uow, household_id=household.id, year=2026, month=9, fixed_amounts={})

    with pytest.raises(PeriodAlreadyBilledError):
        correct_reading(uow, reading_id=september.id, value=Decimal(150))
