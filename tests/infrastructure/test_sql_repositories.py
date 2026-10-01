from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from kommunalka.domain import (
    Bill,
    FixedBillLine,
    Household,
    Meter,
    MeteredBillLine,
    Reading,
    Service,
    TariffPeriod,
    Unit,
)
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork

household = Household(name="Home", address="Main st, 1")
gas = Service(name="Gas", unit=Unit.CUBIC_METER)
transport = Service(name="Gas transportation")
meter = Meter(
    household_id=household.id,
    service_id=gas.id,
    serial_number="G-1",
    label="Boiler",
    installed_on=date(2025, 1, 1),
)


@pytest.fixture
def saved(uow: SqlUnitOfWork) -> None:
    with uow:
        uow.households.save(household)
        uow.services.save(gas)
        uow.services.save(transport)
        uow.meters.save(meter)
        uow.commit()


def test_household_and_service_round_trip(uow: SqlUnitOfWork) -> None:
    with uow:
        uow.households.save(household)
        uow.services.save(gas)
        uow.services.save(transport)
        uow.commit()

    with uow:
        assert uow.households.get(household.id) == household
        assert uow.households.list_all() == [household]
        assert uow.services.get(gas.id) == gas
        assert uow.services.get(transport.id) == transport
        assert uow.services.get(uuid4()) is None


@pytest.mark.usefixtures("saved")
def test_meter_save_updates_existing(uow: SqlUnitOfWork) -> None:
    removed = replace(meter, removed_on=date(2026, 10, 15))

    with uow:
        uow.meters.save(removed)
        uow.commit()

    with uow:
        assert uow.meters.get(meter.id) == removed
        assert uow.meters.list_by_household(household.id) == [removed]


@pytest.mark.usefixtures("saved")
def test_reading_keeps_exact_decimal(uow: SqlUnitOfWork) -> None:
    first = Reading(meter_id=meter.id, value=Decimal("0.1"), taken_on=date(2026, 9, 2))
    second = Reading(
        meter_id=meter.id,
        value=Decimal("12345.678"),
        taken_on=date(2026, 10, 3),
        previous_taken_on=first.taken_on,
    )

    with uow:
        uow.readings.save(second)
        uow.readings.save(first)
        uow.commit()

    with uow:
        assert uow.readings.list_by_meter(meter.id) == [first, second]
        assert uow.readings.get(first.id) == first


@pytest.mark.usefixtures("saved")
def test_tariff_period_round_trip(uow: SqlUnitOfWork) -> None:
    tariff = TariffPeriod(
        service_id=gas.id,
        price=Decimal("0.7812"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )

    with uow:
        uow.tariff_periods.save(tariff)
        uow.commit()

    with uow:
        assert uow.tariff_periods.list_by_service(gas.id) == [tariff]
        assert uow.tariff_periods.list_all() == [tariff]


@pytest.mark.usefixtures("saved")
def test_bill_round_trip_with_both_line_kinds(uow: SqlUnitOfWork) -> None:
    bill = Bill(
        household_id=household.id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        lines=(
            MeteredBillLine(service_id=gas.id, quantity=Decimal("42.5"), price=Decimal("0.78")),
            FixedBillLine(service_id=transport.id, amount=Decimal("12.30")),
        ),
    )
    empty = Bill(
        household_id=household.id,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        lines=(),
    )

    with uow:
        uow.bills.save(bill)
        uow.bills.save(empty)
        uow.commit()

    with uow:
        [loaded, loaded_empty] = uow.bills.list_by_household(household.id)
    assert loaded.id == bill.id
    assert set(loaded.lines) == set(bill.lines)
    assert loaded.total == Decimal("45.45")
    assert loaded_empty == empty


def test_leaving_without_commit_rolls_back(uow: SqlUnitOfWork) -> None:
    with uow:
        uow.households.save(household)

    with uow:
        assert uow.households.list_all() == []


def test_error_rolls_back(uow: SqlUnitOfWork) -> None:
    with pytest.raises(RuntimeError), uow:
        uow.households.save(household)
        raise RuntimeError

    with uow:
        assert uow.households.get(household.id) is None


@pytest.mark.usefixtures("saved")
def test_database_enforces_unique_serial_number(uow: SqlUnitOfWork) -> None:
    duplicate = replace(meter, id=uuid4(), label="Stove")

    with pytest.raises(IntegrityError), uow:
        uow.meters.save(duplicate)


@pytest.mark.usefixtures("saved")
def test_database_enforces_one_reading_per_month(uow: SqlUnitOfWork) -> None:
    with pytest.raises(IntegrityError), uow:
        uow.readings.save(Reading(meter_id=meter.id, value=Decimal(1), taken_on=date(2026, 10, 2)))
        uow.readings.save(Reading(meter_id=meter.id, value=Decimal(2), taken_on=date(2026, 10, 4)))


def test_database_enforces_foreign_keys(uow: SqlUnitOfWork) -> None:
    with pytest.raises(IntegrityError), uow:
        uow.meters.save(meter)
