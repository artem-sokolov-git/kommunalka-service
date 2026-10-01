from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from kommunalka.application.exceptions import NotFoundError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import install_meter, remove_meter, submit_reading
from kommunalka.domain import DomainError, DuplicateMeterError, Household, Meter, Service


def test_installs_meter(uow: UnitOfWork, gas_meter: Meter) -> None:
    assert uow.meters.get(gas_meter.id) == gas_meter


def test_rejects_unknown_household(uow: UnitOfWork, gas: Service) -> None:
    with pytest.raises(NotFoundError):
        install_meter(
            uow,
            household_id=uuid4(),
            service_id=gas.id,
            serial_number="G-1",
            label="Boiler",
            installed_on=date(2025, 1, 1),
        )


def test_rejects_unmetered_service(
    uow: UnitOfWork, household: Household, transport: Service
) -> None:
    with pytest.raises(DomainError):
        install_meter(
            uow,
            household_id=household.id,
            service_id=transport.id,
            serial_number="T-1",
            label="Pipe",
            installed_on=date(2025, 1, 1),
        )


def test_rejects_duplicate_serial_number(
    uow: UnitOfWork, household: Household, gas: Service, gas_meter: Meter
) -> None:
    with pytest.raises(DuplicateMeterError):
        install_meter(
            uow,
            household_id=household.id,
            service_id=gas.id,
            serial_number=gas_meter.serial_number,
            label="Stove",
            installed_on=date(2025, 1, 1),
        )


def test_removes_meter(uow: UnitOfWork, gas_meter: Meter) -> None:
    removed = remove_meter(uow, meter_id=gas_meter.id, removed_on=date(2026, 10, 15))

    assert uow.meters.get(gas_meter.id) == removed
    assert not removed.is_active


def test_rejects_removing_twice(uow: UnitOfWork, gas_meter: Meter) -> None:
    remove_meter(uow, meter_id=gas_meter.id, removed_on=date(2026, 10, 15))

    with pytest.raises(DomainError):
        remove_meter(uow, meter_id=gas_meter.id, removed_on=date(2026, 10, 16))


def test_rejects_removal_before_last_reading(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit_reading(uow, meter_id=gas_meter.id, value=Decimal(1), taken_on=date(2026, 10, 2))

    with pytest.raises(DomainError):
        remove_meter(uow, meter_id=gas_meter.id, removed_on=date(2026, 10, 1))
    assert uow.meters.get(gas_meter.id) == gas_meter
