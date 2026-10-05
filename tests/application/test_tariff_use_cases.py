from datetime import date
from decimal import Decimal

import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import set_tariff
from kommunalka.domain import OverlappingTariffPeriodError, Service, TariffPeriod


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


def test_sets_monthly_tariff_for_unmetered_service(uow: UnitOfWork, transport: Service) -> None:
    tariff = set_tariff(
        uow, service_id=transport.id, price=Decimal("300.78"), valid_from=date(2026, 1, 1)
    )

    assert tariff.valid_to is None
    assert uow.tariff_periods.list_by_service(transport.id) == [tariff]


def test_open_ended_tariff_blocks_later_periods(uow: UnitOfWork, gas: Service) -> None:
    set_tariff(uow, service_id=gas.id, price=Decimal(1), valid_from=date(2026, 1, 1))

    with pytest.raises(OverlappingTariffPeriodError):
        set_tariff(uow, service_id=gas.id, price=Decimal(2), valid_from=date(2030, 1, 1))
