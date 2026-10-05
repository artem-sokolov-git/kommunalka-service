from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from kommunalka.domain import (
    DateRange,
    DomainError,
    DuplicateReadingError,
    Meter,
    Reading,
    ensure_unique_reading,
    next_reading,
    readings_for_month,
)

TODAY = date(2026, 12, 31)

METER_ID = uuid4()
METER = Meter(
    household_id=uuid4(),
    service_id=uuid4(),
    serial_number="SN-1",
    label="Kitchen",
    installed_on=date(2025, 1, 1),
    removed_on=date(2026, 12, 31),
    id=METER_ID,
)


def make_reading(value: str, taken_on: date, previous_taken_on: date | None = None) -> Reading:
    return Reading(
        meter_id=METER_ID,
        value=Decimal(value),
        taken_on=taken_on,
        previous_taken_on=previous_taken_on,
    )


def test_rejects_negative_value() -> None:
    with pytest.raises(DomainError):
        make_reading("-1", date(2026, 10, 2))


def test_rejects_previous_date_not_earlier() -> None:
    with pytest.raises(DomainError):
        make_reading("1", date(2026, 10, 2), previous_taken_on=date(2026, 10, 2))


def test_period_is_between_readings() -> None:
    assert make_reading("1", date(2026, 10, 2)).period is None
    assert make_reading("1", date(2026, 10, 2), date(2026, 9, 3)).period == DateRange(
        date(2026, 9, 3), date(2026, 10, 2)
    )


def test_billing_period_is_previous_month() -> None:
    assert make_reading("1", date(2026, 10, 2)).billing_period == DateRange(
        date(2026, 9, 1), date(2026, 9, 30)
    )


def test_consumption_since_previous() -> None:
    previous = make_reading("100", date(2026, 9, 3))
    current = make_reading("142.5", date(2026, 10, 2), previous.taken_on)

    assert current.consumption_since(previous) == Decimal("42.5")


def test_consumption_requires_matching_previous() -> None:
    current = make_reading("142.5", date(2026, 10, 2), date(2026, 9, 3))

    with pytest.raises(DomainError):
        current.consumption_since(make_reading("100", date(2026, 9, 4)))
    with pytest.raises(DomainError):
        current.consumption_since(
            Reading(meter_id=uuid4(), value=Decimal(100), taken_on=date(2026, 9, 3))
        )


def test_consumption_rejects_decreased_value() -> None:
    previous = make_reading("100", date(2026, 9, 3))
    current = make_reading("99", date(2026, 10, 2), previous.taken_on)

    with pytest.raises(DomainError):
        current.consumption_since(previous)


def test_one_reading_per_meter_and_month() -> None:
    existing = make_reading("1", date(2026, 10, 2))

    ensure_unique_reading(existing, [existing])
    ensure_unique_reading(make_reading("2", date(2026, 11, 2)), [existing])
    with pytest.raises(DuplicateReadingError):
        ensure_unique_reading(make_reading("2", date(2026, 10, 4)), [existing])


def test_next_reading_follows_last() -> None:
    first = next_reading(METER, None, value=Decimal(100), taken_on=date(2026, 9, 2), today=TODAY)
    second = next_reading(METER, first, value=Decimal(120), taken_on=date(2026, 10, 3), today=TODAY)

    assert first.previous_taken_on is None
    assert second.previous_taken_on == first.taken_on
    assert second.consumption_since(first) == Decimal(20)


@pytest.mark.parametrize(
    ("taken_on", "value"),
    [
        (date(2026, 9, 2), "120"),  # not after the last one
        (date(2026, 10, 3), "99"),  # value decreased
        (date(2027, 1, 2), "120"),  # in the future
    ],
)
def test_next_reading_rejects(taken_on: date, value: str) -> None:
    last = make_reading("100", date(2026, 9, 2))

    with pytest.raises(DomainError):
        next_reading(METER, last, value=Decimal(value), taken_on=taken_on, today=TODAY)


def test_readings_for_month() -> None:
    august = make_reading("100", date(2026, 8, 3))
    september = make_reading("120", date(2026, 9, 2), previous_taken_on=august.taken_on)

    assert readings_for_month([august, september], september.billing_period) == (
        august,
        september,
    )
    assert readings_for_month([august, september], august.billing_period) == (None, august)
    assert readings_for_month([august], september.billing_period) == (None, None)


def test_next_reading_rejects_future_date() -> None:
    with pytest.raises(DomainError, match="in the future"):
        next_reading(
            METER, None, value=Decimal(1), taken_on=date(2026, 10, 6), today=date(2026, 10, 5)
        )


def test_next_reading_rejects_meter_out_of_service() -> None:
    with pytest.raises(DomainError, match="not in service"):
        next_reading(
            METER, None, value=Decimal(1), taken_on=date(2027, 1, 2), today=date(2027, 2, 1)
        )
