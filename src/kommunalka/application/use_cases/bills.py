from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from uuid import UUID

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases._common import require
from kommunalka.domain import Bill, DateRange, ensure_unique_bill
from kommunalka.domain.services import calculate_bill


def issue_bill(
    uow: UnitOfWork,
    *,
    household_id: UUID,
    year: int,
    month: int,
    fixed_amounts: Mapping[UUID, Decimal],
) -> Bill:
    """Calculate and store the household bill for a month.

    `fixed_amounts` are ready amounts of unmetered services, e.g. gas transportation.
    """
    period = DateRange.month_of(date(year, month, 1))
    with uow:
        require(uow.households.get(household_id), "Household", household_id)
        meters = uow.meters.list_by_household(household_id)
        bill = calculate_bill(
            household_id=household_id,
            period=period,
            services=uow.services.list_all(),
            meters=meters,
            readings=[r for meter in meters for r in uow.readings.list_by_meter(meter.id)],
            tariff_periods=uow.tariff_periods.list_all(),
            fixed_amounts=fixed_amounts,
        )
        ensure_unique_bill(bill, uow.bills.list_by_household(household_id))
        uow.bills.save(bill)
        uow.commit()
    return bill
