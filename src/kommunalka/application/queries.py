"""Read-only use cases."""

from uuid import UUID

from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases._common import require
from kommunalka.domain import Bill, Household, Meter, Reading, Service, TariffPeriod


def list_households(uow: UnitOfWork) -> list[Household]:
    with uow:
        return uow.households.list_all()


def get_household(uow: UnitOfWork, household_id: UUID) -> Household:
    with uow:
        return require(uow.households.get(household_id), "Household", household_id)


def list_services(uow: UnitOfWork) -> list[Service]:
    with uow:
        return uow.services.list_all()


def list_meters(uow: UnitOfWork, household_id: UUID) -> list[Meter]:
    with uow:
        require(uow.households.get(household_id), "Household", household_id)
        return uow.meters.list_by_household(household_id)


def list_readings(uow: UnitOfWork, meter_id: UUID) -> list[Reading]:
    with uow:
        require(uow.meters.get(meter_id), "Meter", meter_id)
        return uow.readings.list_by_meter(meter_id)


def list_tariff_periods(uow: UnitOfWork, service_id: UUID) -> list[TariffPeriod]:
    with uow:
        require(uow.services.get(service_id), "Service", service_id)
        return uow.tariff_periods.list_by_service(service_id)


def list_bills(uow: UnitOfWork, household_id: UUID) -> list[Bill]:
    with uow:
        require(uow.households.get(household_id), "Household", household_id)
        return uow.bills.list_by_household(household_id)
