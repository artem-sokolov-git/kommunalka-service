from collections.abc import Iterable, Mapping
from decimal import Decimal
from uuid import UUID

from kommunalka.domain.entities.bill import Bill
from kommunalka.domain.entities.meter import Meter
from kommunalka.domain.entities.reading import Reading, readings_for_month
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
    Unmetered services are charged their monthly tariff, unless `fixed_amounts` sets the amount.
    """
    services_by_id = {service.id: service for service in services}
    readings = list(readings)
    tariff_periods = list(tariff_periods)

    consumption: dict[UUID, Decimal] = {}
    for meter in meters:
        if meter.household_id != household_id or not meter.is_in_service_during(period):
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
    for service in services_by_id.values():
        if service.is_metered or service.id in fixed_amounts:
            continue
        monthly = _find_tariff_or_none(service.id, period, tariff_periods)
        if monthly is not None:
            lines.append(FixedBillLine(service_id=service.id, amount=monthly.price))

    return Bill(
        household_id=household_id,
        period_start=period.start,
        period_end=period.end,
        lines=tuple(lines),
    )


def _get_service(services_by_id: Mapping[UUID, Service], service_id: UUID) -> Service:
    try:
        return services_by_id[service_id]
    except KeyError:
        raise DomainError(f"Unknown service {service_id}") from None


def _consumption(meter: Meter, period: DateRange, readings: list[Reading]) -> Decimal:
    previous, current = readings_for_month(
        (reading for reading in readings if reading.meter_id == meter.id), period
    )
    if current is None:
        raise MissingReadingError(f"Meter {meter.label!r} has no reading for {period.start:%Y-%m}")
    if current.previous_taken_on is None:
        return Decimal(0)
    if previous is None:
        raise MissingReadingError(
            f"Meter {meter.label!r} has no reading on {current.previous_taken_on}"
        )
    return current.consumption_since(previous)


def _find_tariff(
    service_id: UUID, period: DateRange, tariff_periods: list[TariffPeriod]
) -> TariffPeriod:
    tariff_period = _find_tariff_or_none(service_id, period, tariff_periods)
    if tariff_period is None:
        raise MissingTariffError(f"No tariff for service {service_id} in {period.start:%Y-%m}")
    return tariff_period


def _find_tariff_or_none(
    service_id: UUID, period: DateRange, tariff_periods: list[TariffPeriod]
) -> TariffPeriod | None:
    return next(
        (t for t in tariff_periods if t.service_id == service_id and t.covers(period)), None
    )
