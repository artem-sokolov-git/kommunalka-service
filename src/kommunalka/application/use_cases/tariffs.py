from datetime import date
from decimal import Decimal
from uuid import UUID

from kommunalka.application._common import require
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.domain import (
    TariffPeriod,
    ensure_no_overlap,
    ensure_price_not_billed,
    next_tariff_period,
)


def set_tariff(
    uow: UnitOfWork,
    *,
    service_id: UUID,
    price: Decimal,
    valid_from: date,
    valid_to: date | None = None,
) -> TariffPeriod:
    """Set a price per unit for a metered service or per month for an unmetered one."""
    tariff_period = TariffPeriod(
        service_id=service_id, price=price, valid_from=valid_from, valid_to=valid_to
    )
    with uow:
        require(uow.services.get(service_id), "Service", service_id)
        ensure_no_overlap(tariff_period, uow.tariff_periods.list_by_service(service_id))
        uow.tariff_periods.save(tariff_period)
        uow.commit()
    return tariff_period


def change_price(
    uow: UnitOfWork, *, service_id: UUID, price: Decimal, valid_from: date
) -> TariffPeriod:
    """Start a new price on the first day of a month, closing the current one the day before."""
    with uow:
        require(uow.services.get(service_id), "Service", service_id)
        closed, new = next_tariff_period(
            uow.tariff_periods.list_by_service(service_id),
            service_id=service_id,
            price=price,
            valid_from=valid_from,
        )
        for household in uow.households.list_all():
            ensure_price_not_billed(
                service_id, valid_from, uow.bills.list_by_household(household.id)
            )
        if closed is not None:
            uow.tariff_periods.save(closed)
        uow.tariff_periods.save(new)
        uow.commit()
    return new
