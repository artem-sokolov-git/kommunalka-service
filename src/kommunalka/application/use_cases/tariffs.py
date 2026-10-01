from datetime import date
from decimal import Decimal
from uuid import UUID

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases._common import require
from kommunalka.domain import DomainError, TariffPeriod, ensure_no_overlap


def set_tariff(
    uow: UnitOfWork,
    *,
    service_id: UUID,
    price: Decimal,
    valid_from: date,
    valid_to: date,
) -> TariffPeriod:
    tariff_period = TariffPeriod(
        service_id=service_id, price=price, valid_from=valid_from, valid_to=valid_to
    )
    with uow:
        service = require(uow.services.get(service_id), "Service", service_id)
        if not service.is_metered:
            raise DomainError(f"Service {service.name!r} is unmetered")
        ensure_no_overlap(tariff_period, uow.tariff_periods.list_by_service(service_id))
        uow.tariff_periods.save(tariff_period)
        uow.commit()
    return tariff_period
