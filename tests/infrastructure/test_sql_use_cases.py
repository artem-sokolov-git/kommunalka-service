from datetime import date
from decimal import Decimal

from kommunalka.application.use_cases import (
    add_service,
    install_meter,
    issue_bill,
    register_household,
    set_tariff,
    submit_reading,
)
from kommunalka.domain import Unit
from kommunalka.infrastructure.db.unit_of_work import SqlUnitOfWork

TODAY = date(2026, 12, 31)


def test_issues_bill_end_to_end(uow: SqlUnitOfWork) -> None:
    household = register_household(uow, name="Home", address="Main st, 1")
    gas = add_service(uow, name="Gas", unit=Unit.CUBIC_METER)
    transport = add_service(uow, name="Gas transportation")
    meter = install_meter(
        uow,
        household_id=household.id,
        service_id=gas.id,
        serial_number="G-1",
        label="Boiler",
        installed_on=date(2025, 1, 1),
    )
    set_tariff(
        uow,
        service_id=gas.id,
        price=Decimal("0.78"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    submit_reading(
        uow, meter_id=meter.id, value=Decimal(100), taken_on=date(2026, 9, 2), today=TODAY
    )
    submit_reading(
        uow, meter_id=meter.id, value=Decimal("142.5"), taken_on=date(2026, 10, 3), today=TODAY
    )

    bill = issue_bill(
        uow,
        household_id=household.id,
        year=2026,
        month=9,
        fixed_amounts={transport.id: Decimal("12.30")},
    )

    assert bill.total == Decimal("45.45")
    with uow:
        [stored] = uow.bills.list_by_household(household.id)
    assert stored.total == bill.total
    assert set(stored.lines) == set(bill.lines)
