from datetime import date
from decimal import Decimal
from uuid import UUID

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases._common import require
from kommunalka.domain import TariffPeriod, ensure_no_overlap


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
