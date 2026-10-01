from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from kommunalka.domain import (
    Bill,
    DateRange,
    DomainError,
    FixedBillLine,
    Household,
    Meter,
    MeteredBillLine,
    MissingReadingError,
    MissingTariffError,
    Reading,
    Service,
    TariffPeriod,
    Unit,
)
from kommunalka.domain.services import calculate_bill

SEPTEMBER = DateRange.month_of(date(2026, 9, 1))

household = Household(name="Home", address="Main st, 1")
gas = Service(name="Gas", unit=Unit.CUBIC_METER)
electricity = Service(name="Electricity", unit=Unit.KWH)
transport = Service(name="Gas transportation")
tariffs = [
    TariffPeriod(
        service_id=gas.id,
        price=Decimal("0.78"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    ),
    TariffPeriod(
        service_id=electricity.id,
        price=Decimal("0.25"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    ),
]


def make_meter(
    service: Service,
    label: str,
    installed_on: date = date(2025, 1, 1),
    removed_on: date | None = None,
    household_id: UUID = household.id,
) -> Meter:
    return Meter(
        household_id=household_id,
        service_id=service.id,
        serial_number=str(uuid4()),
        label=label,
        installed_on=installed_on,
        removed_on=removed_on,
    )


def september_readings(meter: Meter, before: str, after: str) -> list[Reading]:
    return [
        Reading(meter_id=meter.id, value=Decimal(before), taken_on=date(2026, 9, 2)),
        Reading(
            meter_id=meter.id,
            value=Decimal(after),
            taken_on=date(2026, 10, 3),
            previous_taken_on=date(2026, 9, 2),
        ),
    ]


def calculate(
    meters: list[Meter],
    readings: list[Reading],
    fixed_amounts: Mapping[UUID, Decimal] | None = None,
    tariff_periods: list[TariffPeriod] = tariffs,
) -> Bill:
    return calculate_bill(
        household_id=household.id,
        period=SEPTEMBER,
        services=[gas, electricity, transport],
        meters=meters,
        readings=readings,
        tariff_periods=tariff_periods,
        fixed_amounts=fixed_amounts or {},
    )


def test_calculates_metered_and_fixed_lines() -> None:
    gas_meter = make_meter(gas, "Boiler")
    power_meter = make_meter(electricity, "Hall")

    bill = calculate(
        [gas_meter, power_meter],
        september_readings(gas_meter, "100", "142.5")
        + september_readings(power_meter, "5000", "5210"),
        fixed_amounts={transport.id: Decimal("12.30")},
    )

    assert bill.household_id == household.id
    assert bill.period == SEPTEMBER
    assert set(bill.lines) == {
        MeteredBillLine(service_id=gas.id, quantity=Decimal("42.5"), price=Decimal("0.78")),
        MeteredBillLine(service_id=electricity.id, quantity=Decimal(210), price=Decimal("0.25")),
        FixedBillLine(service_id=transport.id, amount=Decimal("12.30")),
    }
    assert bill.total == Decimal("97.95")


def test_sums_meters_of_one_service() -> None:
    kitchen = make_meter(electricity, "Kitchen")
    hall = make_meter(electricity, "Hall")

    bill = calculate(
        [kitchen, hall],
        september_readings(kitchen, "10", "20") + september_readings(hall, "100", "105"),
    )

    assert bill.lines == (
        MeteredBillLine(service_id=electricity.id, quantity=Decimal(15), price=Decimal("0.25")),
    )


def test_first_reading_is_baseline() -> None:
    meter = make_meter(gas, "Boiler", installed_on=date(2026, 9, 15))
    baseline = Reading(meter_id=meter.id, value=Decimal(7), taken_on=date(2026, 10, 2))

    bill = calculate([meter], [baseline])

    assert bill.total == Decimal(0)


def test_skips_meters_out_of_service_and_of_other_households() -> None:
    meters = [
        make_meter(gas, "New", installed_on=date(2026, 10, 1)),
        make_meter(gas, "Old", removed_on=date(2026, 8, 31)),
        make_meter(gas, "Foreign", household_id=uuid4()),
    ]

    assert calculate(meters, []).lines == ()


def test_requires_reading_for_the_month() -> None:
    meter = make_meter(gas, "Boiler")

    with pytest.raises(MissingReadingError):
        calculate([meter], september_readings(meter, "1", "2")[:1])


def test_requires_previous_reading() -> None:
    meter = make_meter(gas, "Boiler")

    with pytest.raises(MissingReadingError):
        calculate([meter], september_readings(meter, "1", "2")[1:])


def test_requires_tariff_covering_the_month() -> None:
    meter = make_meter(gas, "Boiler")
    partial = TariffPeriod(
        service_id=gas.id,
        price=Decimal(1),
        valid_from=date(2026, 9, 10),
        valid_to=date(2026, 12, 31),
    )

    with pytest.raises(MissingTariffError):
        calculate([meter], september_readings(meter, "1", "2"), tariff_periods=[partial])


def test_rejects_ready_amount_for_metered_service() -> None:
    with pytest.raises(DomainError):
        calculate([], [], fixed_amounts={gas.id: Decimal(1)})


def test_rejects_meter_of_unmetered_service() -> None:
    with pytest.raises(DomainError):
        calculate([make_meter(transport, "Pipe")], [])


def test_rejects_unknown_service() -> None:
    with pytest.raises(DomainError):
        calculate([], [], fixed_amounts={uuid4(): Decimal(1)})
