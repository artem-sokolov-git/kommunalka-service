from collections.abc import Iterable, Mapping
from decimal import Decimal
from uuid import UUID

from kommunalka.domain.entities.bill import Bill
from kommunalka.domain.entities.meter import Meter
from kommunalka.domain.entities.reading import Reading
from kommunalka.domain.entities.service import Service
from kommunalka.domain.entities.tariff import TariffPeriod
from kommunalka.domain.exceptions import DomainError, MissingReadingError, MissingTariffError
from kommunalka.domain.value_objects import BillLine, DateRange, FixedBillLine, MeteredBillLine


def calculate_bill(
    *,
    household_id: UUID,
    period: DateRange,
    services: Iterable[Service],
    meters: Iterable[Meter],
    readings: Iterable[Reading],
    tariff_periods: Iterable[TariffPeriod],
    fixed_amounts: Mapping[UUID, Decimal],
) -> Bill:
    """Build the household bill for a billing month.

    Every household meter in service during the month must have a reading for it.
    The first reading of a meter is a baseline and adds no consumption.
    Consumption of several meters of one service is summed into one line.
    """
    services_by_id = {service.id: service for service in services}
    readings = list(readings)
    tariff_periods = list(tariff_periods)

    consumption: dict[UUID, Decimal] = {}
    for meter in meters:
        if meter.household_id != household_id or not _in_service_during(meter, period):
            continue
        if not _get_service(services_by_id, meter.service_id).is_metered:
            raise DomainError(f"Meter {meter.label!r} belongs to an unmetered service")
        consumption[meter.service_id] = consumption.get(meter.service_id, Decimal(0)) + (
            _consumption(meter, period, readings)
        )

    lines: list[BillLine] = [
        MeteredBillLine(
            service_id=service_id,
            quantity=quantity,
            price=_find_tariff(service_id, period, tariff_periods).price,
        )
        for service_id, quantity in consumption.items()
    ]
    for service_id, amount in fixed_amounts.items():
        if _get_service(services_by_id, service_id).is_metered:
            raise DomainError("Ready amount is allowed only for unmetered services")
        lines.append(FixedBillLine(service_id=service_id, amount=amount))

    return Bill(
        household_id=household_id,
        period_start=period.start,
        period_end=period.end,
        lines=tuple(lines),
    )


def _in_service_during(meter: Meter, period: DateRange) -> bool:
    return meter.installed_on <= period.end and (
        meter.removed_on is None or meter.removed_on >= period.start
    )


def _get_service(services_by_id: Mapping[UUID, Service], service_id: UUID) -> Service:
    try:
        return services_by_id[service_id]
    except KeyError:
        raise DomainError(f"Unknown service {service_id}") from None


def _consumption(meter: Meter, period: DateRange, readings: list[Reading]) -> Decimal:
    meter_readings = [reading for reading in readings if reading.meter_id == meter.id]
    current = next((r for r in meter_readings if r.billing_period == period), None)
    if current is None:
        raise MissingReadingError(f"Meter {meter.label!r} has no reading for {period.start:%Y-%m}")
    if current.previous_taken_on is None:
        return Decimal(0)
    previous = next((r for r in meter_readings if r.taken_on == current.previous_taken_on), None)
    if previous is None:
        raise MissingReadingError(
            f"Meter {meter.label!r} has no reading on {current.previous_taken_on}"
        )
    return current.consumption_since(previous)


def _find_tariff(
    service_id: UUID, period: DateRange, tariff_periods: list[TariffPeriod]
) -> TariffPeriod:
    for tariff_period in tariff_periods:
        if tariff_period.service_id == service_id and tariff_period.covers(period):
            return tariff_period
    raise MissingTariffError(f"No tariff for service {service_id} in {period.start:%Y-%m}")
