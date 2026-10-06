from datetime import date
from decimal import Decimal

import pytest

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import (
    change_price,
    issue_bill,
    set_tariff,
    undo_price_change,
)
from kommunalka.domain import (
    Household,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
    Service,
    TariffPeriod,
)


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


def test_change_price_closes_current_period(uow: UnitOfWork, transport: Service) -> None:
    old = set_tariff(
        uow, service_id=transport.id, price=Decimal("300.78"), valid_from=date(2025, 12, 1)
    )

    new = change_price(
        uow, service_id=transport.id, price=Decimal("320"), valid_from=date(2027, 1, 1)
    )

    periods = {period.id: period for period in uow.tariff_periods.list_by_service(transport.id)}
    assert periods[old.id].valid_to == date(2026, 12, 31)
    assert periods[new.id].valid_to is None


def test_undo_price_change_restores_the_previous_price(uow: UnitOfWork, transport: Service) -> None:
    old = set_tariff(
        uow, service_id=transport.id, price=Decimal("300.78"), valid_from=date(2025, 12, 1)
    )
    change_price(uow, service_id=transport.id, price=Decimal(320), valid_from=date(2027, 1, 1))

    current = undo_price_change(uow, service_id=transport.id)

    assert current is not None
    assert current.id == old.id
    assert uow.tariff_periods.list_by_service(transport.id) == [current]
    assert current.valid_to is None


def test_price_used_by_a_bill_cannot_be_undone(
    uow: UnitOfWork, household: Household, transport: Service
) -> None:
    set_tariff(uow, service_id=transport.id, price=Decimal("300.78"), valid_from=date(2025, 12, 1))
    change_price(uow, service_id=transport.id, price=Decimal(320), valid_from=date(2026, 9, 1))
    issue_bill(uow, household_id=household.id, year=2026, month=9, fixed_amounts={})

    with pytest.raises(PeriodAlreadyBilledError):
        undo_price_change(uow, service_id=transport.id)
    assert len(uow.tariff_periods.list_by_service(transport.id)) == 2
