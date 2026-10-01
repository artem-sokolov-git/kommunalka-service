from datetime import date
from decimal import Decimal

import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import set_tariff
from kommunalka.domain import DomainError, OverlappingTariffPeriodError, Service, TariffPeriod


def test_sets_tariff(uow: UnitOfWork, gas: Service, gas_tariff: TariffPeriod) -> None:
    assert uow.tariff_periods.list_by_service(gas.id) == [gas_tariff]


def test_rejects_overlapping_period(
    uow: UnitOfWork, gas: Service, gas_tariff: TariffPeriod
) -> None:
    with pytest.raises(OverlappingTariffPeriodError):
        set_tariff(
            uow,
            service_id=gas.id,
            price=Decimal(1),
            valid_from=date(2026, 7, 1),
            valid_to=date(2027, 6, 30),
        )
    assert uow.tariff_periods.list_by_service(gas.id) == [gas_tariff]


def test_rejects_unmetered_service(uow: UnitOfWork, transport: Service) -> None:
    with pytest.raises(DomainError):
        set_tariff(
            uow,
            service_id=transport.id,
            price=Decimal(1),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
