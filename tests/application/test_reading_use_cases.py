from datetime import date
from decimal import Decimal

import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import (
    add_service,
    correct_reading,
    install_meter,
    issue_bill,
    register_household,
    remove_meter,
    submit_reading,
    submit_readings,
    submit_readings_and_issue_bill,
)
from kommunalka.domain import (
    DomainError,
    DuplicateReadingError,
    Household,
    Meter,
    MissingTariffError,
    PeriodAlreadyBilledError,
    Reading,
    TariffPeriod,
    Unit,
)

TODAY = date(2026, 12, 31)


def submit(uow: UnitOfWork, meter: Meter, value: str, taken_on: date) -> Reading:
    return submit_reading(
        uow, meter_id=meter.id, value=Decimal(value), taken_on=taken_on, today=TODAY
    )


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


@pytest.fixture
def power_meter(uow: UnitOfWork, household: Household) -> Meter:
    power = add_service(uow, name="Electricity", unit=Unit.KWH)
    return install_meter(
        uow,
        household_id=household.id,
        service_id=power.id,
        serial_number="E-1",
        label="Hall",
        installed_on=date(2025, 1, 1),
    )


def test_submits_readings_of_several_meters(
    uow: UnitOfWork, household: Household, gas_meter: Meter, power_meter: Meter
) -> None:
    readings = submit_readings(
        uow,
        household_id=household.id,
        taken_on=date(2026, 10, 2),
        values={gas_meter.id: Decimal(100), power_meter.id: Decimal(5000)},
        today=TODAY,
    )

    assert {r.meter_id for r in readings} == {gas_meter.id, power_meter.id}


def test_submits_all_readings_or_none(
    uow: UnitOfWork, household: Household, gas_meter: Meter, power_meter: Meter
) -> None:
    submit(uow, power_meter, "5000", date(2026, 9, 2))

    with pytest.raises(DomainError, match="Hall: Reading value decreased"):
        submit_readings(
            uow,
            household_id=household.id,
            taken_on=date(2026, 10, 2),
            values={gas_meter.id: Decimal(100), power_meter.id: Decimal(4999)},
            today=TODAY,
        )

    assert uow.readings.list_by_meter(gas_meter.id) == []


def test_rejects_meter_of_another_household(
    uow: UnitOfWork, household: Household, gas_meter: Meter
) -> None:
    other = register_household(uow, name="Other", address="Other st, 2")

    with pytest.raises(DomainError, match="belongs to another household"):
        submit_readings(
            uow,
            household_id=other.id,
            taken_on=date(2026, 10, 2),
            values={gas_meter.id: Decimal(100)},
            today=TODAY,
        )


def test_submits_readings_and_bills_the_month_they_close(
    uow: UnitOfWork, household: Household, gas_meter: Meter, gas_tariff: TariffPeriod
) -> None:
    submit(uow, gas_meter, "100", date(2026, 9, 2))

    bill = submit_readings_and_issue_bill(
        uow,
        household_id=household.id,
        taken_on=date(2026, 10, 2),
        values={gas_meter.id: Decimal(110)},
        fixed_amounts={},
        today=TODAY,
    )

    assert (bill.period_start, bill.total) == (date(2026, 9, 1), Decimal("7.80"))
    assert uow.bills.list_by_household(household.id) == [bill]


def test_keeps_no_readings_if_the_bill_fails(
    uow: UnitOfWork,
    household: Household,
    gas_meter: Meter,
    gas_tariff: TariffPeriod,
    power_meter: Meter,
) -> None:
    submit(uow, gas_meter, "100", date(2026, 9, 2))
    submit(uow, power_meter, "5000", date(2026, 9, 2))

    with pytest.raises(MissingTariffError):
        submit_readings_and_issue_bill(
            uow,
            household_id=household.id,
            taken_on=date(2026, 10, 2),
            values={gas_meter.id: Decimal(110), power_meter.id: Decimal(5100)},
            fixed_amounts={},
            today=TODAY,
        )

    assert len(uow.readings.list_by_meter(gas_meter.id)) == 1
