from dataclasses import replace
from datetime import date
from uuid import UUID

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases._common import require
from kommunalka.domain import DomainError, Meter, ensure_unique_meter


def install_meter(
    uow: UnitOfWork,
    *,
    household_id: UUID,
    service_id: UUID,
    serial_number: str,
    label: str,
    installed_on: date,
) -> Meter:
    meter = Meter(
        household_id=household_id,
        service_id=service_id,
        serial_number=serial_number,
        label=label,
        installed_on=installed_on,
    )
    with uow:
        require(uow.households.get(household_id), "Household", household_id)
        service = require(uow.services.get(service_id), "Service", service_id)
        if not service.is_metered:
            raise DomainError(f"Service {service.name!r} is unmetered")
        ensure_unique_meter(meter, uow.meters.list_all())
        uow.meters.save(meter)
        uow.commit()
    return meter


def remove_meter(uow: UnitOfWork, *, meter_id: UUID, removed_on: date) -> Meter:
    with uow:
        meter = require(uow.meters.get(meter_id), "Meter", meter_id)
        if not meter.is_active:
            raise DomainError(f"Meter {meter.label!r} is already removed")
        if any(r.taken_on > removed_on for r in uow.readings.list_by_meter(meter_id)):
            raise DomainError(f"Meter {meter.label!r} has readings after {removed_on}")
        removed = replace(meter, removed_on=removed_on)
        uow.meters.save(removed)
        uow.commit()
    return removed
