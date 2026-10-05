"""Read-only use cases."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from kommunalka.application._common import require
from kommunalka.application.exceptions import NotFoundError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.domain import (
    Bill,
    BillLine,
    Household,
    Meter,
    Reading,
    Service,
    TariffPeriod,
    readings_for_month,
)


@dataclass(frozen=True, slots=True)
class HouseholdOverview:
    household: Household
    bill_count: int
    last_bill: Bill | None


@dataclass(frozen=True, slots=True)
class HouseholdBills:
    household: Household
    bills: list[Bill]


@dataclass(frozen=True, slots=True)
class MeterReadings:
    """Readings of a meter that a bill line is calculated from."""

    meter: Meter
    previous: Reading | None
    current: Reading


@dataclass(frozen=True, slots=True)
class BillLineDetails:
    line: BillLine
    service: Service
    readings: list[MeterReadings]


@dataclass(frozen=True, slots=True)
class BillDetails:
    household: Household
    bill: Bill
    lines: list[BillLineDetails]
    previous_period: date | None
    next_period: date | None


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


def get_bill(uow: UnitOfWork, household_id: UUID, year: int, month: int) -> Bill:
    return _find_bill(list_bills(uow, household_id), year, month)


def household_overviews(uow: UnitOfWork) -> list[HouseholdOverview]:
    with uow:
        overviews = []
        for household in uow.households.list_all():
            bills = uow.bills.list_by_household(household.id)
            overviews.append(HouseholdOverview(household, len(bills), bills[-1] if bills else None))
        return overviews


def household_bills(uow: UnitOfWork, household_id: UUID) -> HouseholdBills:
    with uow:
        household = require(uow.households.get(household_id), "Household", household_id)
        return HouseholdBills(household, uow.bills.list_by_household(household_id))


def bill_details(uow: UnitOfWork, household_id: UUID, year: int, month: int) -> BillDetails:
    """A bill with the services and meter readings behind each line, and neighbour months."""
    with uow:
        household = require(uow.households.get(household_id), "Household", household_id)
        bills = uow.bills.list_by_household(household_id)
        bill = _find_bill(bills, year, month)
        services = {service.id: service for service in uow.services.list_all()}
        meters = uow.meters.list_by_household(household_id)
        lines = [
            BillLineDetails(
                line=line,
                service=services[line.service_id],
                readings=[
                    meter_readings
                    for meter in meters
                    if meter.service_id == line.service_id
                    and (meter_readings := _meter_readings(uow, meter, bill)) is not None
                ],
            )
            for line in bill.lines
        ]
    index = bills.index(bill)
    return BillDetails(
        household=household,
        bill=bill,
        lines=lines,
        previous_period=bills[index - 1].period_start if index > 0 else None,
        next_period=bills[index + 1].period_start if index + 1 < len(bills) else None,
    )


def _find_bill(bills: list[Bill], year: int, month: int) -> Bill:
    period_start = date(year, month, 1)
    for bill in bills:
        if bill.period_start == period_start:
            return bill
    raise NotFoundError(f"Bill for {period_start:%Y-%m} not found")


def _meter_readings(uow: UnitOfWork, meter: Meter, bill: Bill) -> MeterReadings | None:
    previous, current = readings_for_month(uow.readings.list_by_meter(meter.id), bill.period)
    return None if current is None else MeterReadings(meter, previous, current)
