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
    DateRange,
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


@dataclass(frozen=True, slots=True)
class MeterInput:
    meter: Meter
    service: Service
    last_reading: Reading | None
    last_reading_correctable: bool


@dataclass(frozen=True, slots=True)
class ReadingForm:
    """What a person needs to submit readings taken on a day and bill the months they close."""

    household: Household
    meters: list[MeterInput]
    unbilled_periods: list[DateRange]
    """Months closed by submitted readings but not billed yet, oldest first."""
    last_billed_period: DateRange | None


def reading_form(uow: UnitOfWork, household_id: UUID, taken_on: date) -> ReadingForm:
    with uow:
        household = require(uow.households.get(household_id), "Household", household_id)
        services = {service.id: service for service in uow.services.list_all()}
        billed = {bill.period for bill in uow.bills.list_by_household(household_id)}
        closed: set[DateRange] = set()
        meters = []
        for meter in uow.meters.list_by_household(household_id):
            readings = uow.readings.list_by_meter(meter.id)
            # A baseline reading closes a month without consumption, there is nothing to bill.
            closed.update(r.billing_period for r in readings if r.previous_taken_on is not None)
            if not meter.is_in_service_on(taken_on):
                continue
            last = _last_reading(readings)
            meters.append(
                MeterInput(
                    meter=meter,
                    service=services[meter.service_id],
                    last_reading=last,
                    last_reading_correctable=last is not None and last.billing_period not in billed,
                )
            )
    return ReadingForm(
        household=household,
        meters=meters,
        unbilled_periods=sorted(closed - billed, key=lambda period: period.start),
        last_billed_period=max(billed, key=lambda period: period.start) if billed else None,
    )


@dataclass(frozen=True, slots=True)
class ReadingCorrection:
    household: Household
    meter: Meter
    reading: Reading
    previous: Reading | None


def reading_correction(uow: UnitOfWork, household_id: UUID, reading_id: UUID) -> ReadingCorrection:
    """A reading of the household with the one before it, to correct its value."""
    with uow:
        household = require(uow.households.get(household_id), "Household", household_id)
        reading = require(uow.readings.get(reading_id), "Reading", reading_id)
        meter = require(uow.meters.get(reading.meter_id), "Meter", reading.meter_id)
        if meter.household_id != household_id:
            raise NotFoundError(f"Reading {reading_id} not found")
        previous, _ = readings_for_month(
            uow.readings.list_by_meter(meter.id), reading.billing_period
        )
    return ReadingCorrection(household, meter, reading, previous)


def _last_reading(readings: list[Reading]) -> Reading | None:
    if not readings:
        return None
    return max(readings, key=lambda reading: reading.taken_on)


def _find_bill(bills: list[Bill], year: int, month: int) -> Bill:
    period_start = date(year, month, 1)
    for bill in bills:
        if bill.period_start == period_start:
            return bill
    raise NotFoundError(f"Bill for {period_start:%Y-%m} not found")


def _meter_readings(uow: UnitOfWork, meter: Meter, bill: Bill) -> MeterReadings | None:
    previous, current = readings_for_month(uow.readings.list_by_meter(meter.id), bill.period)
    return None if current is None else MeterReadings(meter, previous, current)
