from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from kommunalka.application._common import require
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.domain import (
    Meter,
    Reading,
    ensure_not_billed,
    ensure_unique_reading,
    next_reading,
)


def submit_reading(uow: UnitOfWork, *, meter_id: UUID, value: Decimal, taken_on: date) -> Reading:
    """Add a reading after the last one of the meter."""
    with uow:
        meter = require(uow.meters.get(meter_id), "Meter", meter_id)
        readings = uow.readings.list_by_meter(meter_id)
        last = max(readings, key=lambda r: r.taken_on, default=None)
        reading = next_reading(meter, last, value=value, taken_on=taken_on)
        ensure_unique_reading(reading, readings)
        _ensure_not_billed(uow, meter, reading)
        uow.readings.save(reading)
        uow.commit()
    return reading


def correct_reading(uow: UnitOfWork, *, reading_id: UUID, value: Decimal) -> Reading:
    """Change the value of a reading whose months are not billed yet."""
    with uow:
        reading = require(uow.readings.get(reading_id), "Reading", reading_id)
        meter = require(uow.meters.get(reading.meter_id), "Meter", reading.meter_id)
        corrected = replace(reading, value=value)
        readings = uow.readings.list_by_meter(meter.id)
        previous = next((r for r in readings if r.taken_on == reading.previous_taken_on), None)
        following = next((r for r in readings if r.previous_taken_on == reading.taken_on), None)
        if previous is not None:
            corrected.consumption_since(previous)
        _ensure_not_billed(uow, meter, corrected)
        if following is not None:
            following.consumption_since(corrected)
            _ensure_not_billed(uow, meter, following)
        uow.readings.save(corrected)
        uow.commit()
    return corrected


def _ensure_not_billed(uow: UnitOfWork, meter: Meter, reading: Reading) -> None:
    ensure_not_billed(
        meter.household_id,
        reading.billing_period,
        uow.bills.list_by_household(meter.household_id),
    )
