from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import (
    add_service,
    install_meter,
    register_household,
    set_tariff,
)
from kommunalka.domain import (
    Bill,
    Household,
    Meter,
    Reading,
    Service,
    TariffPeriod,
    Unit,
)


class _Entity(Protocol):
    @property
    def id(self) -> UUID: ...


class _Store[T: _Entity]:
    def __init__(self) -> None:
        self.items: dict[UUID, T] = {}
        self._snapshot: dict[UUID, T] = {}

    def get(self, entity_id: UUID) -> T | None:
        return self.items.get(entity_id)

    def list_all(self) -> list[T]:
        return list(self.items.values())

    def save(self, entity: T) -> None:
        self.items[entity.id] = entity

    def begin(self) -> None:
        self._snapshot = dict(self.items)

    def rollback(self) -> None:
        self.items = dict(self._snapshot)


class _MeterStore(_Store[Meter]):
    def list_by_household(self, household_id: UUID) -> list[Meter]:
        return [m for m in self.items.values() if m.household_id == household_id]


class _ReadingStore(_Store[Reading]):
    def list_by_meter(self, meter_id: UUID) -> list[Reading]:
        return [r for r in self.items.values() if r.meter_id == meter_id]


class _TariffPeriodStore(_Store[TariffPeriod]):
    def list_by_service(self, service_id: UUID) -> list[TariffPeriod]:
        return [t for t in self.items.values() if t.service_id == service_id]


class _BillStore(_Store[Bill]):
    def list_by_household(self, household_id: UUID) -> list[Bill]:
        return [b for b in self.items.values() if b.household_id == household_id]


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.households = _Store[Household]()
        self.services = _Store[Service]()
        self.meters = _MeterStore()
        self.readings = _ReadingStore()
        self.tariff_periods = _TariffPeriodStore()
        self.bills = _BillStore()
        self._stores: list[_Store] = [
            self.households,
            self.services,
            self.meters,
            self.readings,
            self.tariff_periods,
            self.bills,
        ]
        self._committed = False

    def __enter__(self) -> Self:
        self._committed = False
        for store in self._stores:
            store.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        for store in self._stores:
            store.rollback()


@pytest.fixture
def uow() -> UnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def household(uow: UnitOfWork) -> Household:
    return register_household(uow, name="Home", address="Main st, 1")


@pytest.fixture
def gas(uow: UnitOfWork) -> Service:
    return add_service(uow, name="Gas", unit=Unit.CUBIC_METER)


@pytest.fixture
def transport(uow: UnitOfWork) -> Service:
    return add_service(uow, name="Gas transportation")


@pytest.fixture
def gas_meter(uow: UnitOfWork, household: Household, gas: Service) -> Meter:
    return install_meter(
        uow,
        household_id=household.id,
        service_id=gas.id,
        serial_number="G-1",
        label="Boiler",
        installed_on=date(2025, 1, 1),
    )


@pytest.fixture
def gas_tariff(uow: UnitOfWork, gas: Service) -> TariffPeriod:
    return set_tariff(
        uow,
        service_id=gas.id,
        price=Decimal("0.78"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
