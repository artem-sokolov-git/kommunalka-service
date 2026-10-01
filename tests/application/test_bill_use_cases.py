from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from kommunalka.application.exceptions import NotFoundError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import issue_bill, submit_reading
from kommunalka.domain import (
    DateRange,
    DuplicateBillError,
    FixedBillLine,
    Household,
    Meter,
    MeteredBillLine,
    MissingReadingError,
    Service,
    TariffPeriod,
)


@pytest.fixture
def september_readings(uow: UnitOfWork, gas_meter: Meter) -> None:
    submit_reading(uow, meter_id=gas_meter.id, value=Decimal(100), taken_on=date(2026, 9, 2))
    submit_reading(uow, meter_id=gas_meter.id, value=Decimal("142.5"), taken_on=date(2026, 10, 3))


@pytest.mark.usefixtures("september_readings")
def test_issues_bill(
    uow: UnitOfWork,
    household: Household,
    gas: Service,
    transport: Service,
    gas_tariff: TariffPeriod,
) -> None:
    bill = issue_bill(
        uow,
        household_id=household.id,
        year=2026,
        month=9,
        fixed_amounts={transport.id: Decimal("12.30")},
    )

    assert bill.period == DateRange.month_of(date(2026, 9, 1))
    assert set(bill.lines) == {
        MeteredBillLine(service_id=gas.id, quantity=Decimal("42.5"), price=gas_tariff.price),
        FixedBillLine(service_id=transport.id, amount=Decimal("12.30")),
    }
    assert bill.total == Decimal("45.45")
    assert uow.bills.list_by_household(household.id) == [bill]


@pytest.mark.usefixtures("september_readings", "gas_tariff")
def test_rejects_second_bill_for_month(uow: UnitOfWork, household: Household) -> None:
    issue_bill(uow, household_id=household.id, year=2026, month=9, fixed_amounts={})

    with pytest.raises(DuplicateBillError):
        issue_bill(uow, household_id=household.id, year=2026, month=9, fixed_amounts={})
    assert len(uow.bills.list_by_household(household.id)) == 1


@pytest.mark.usefixtures("gas_meter", "gas_tariff")
def test_rejects_month_without_readings(uow: UnitOfWork, household: Household) -> None:
    with pytest.raises(MissingReadingError):
        issue_bill(uow, household_id=household.id, year=2026, month=9, fixed_amounts={})
    assert uow.bills.list_by_household(household.id) == []


def test_rejects_unknown_household(uow: UnitOfWork) -> None:
    with pytest.raises(NotFoundError):
        issue_bill(uow, household_id=uuid4(), year=2026, month=9, fixed_amounts={})
