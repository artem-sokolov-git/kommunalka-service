from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from kommunalka.domain import (
    DateRange,
    DomainError,
    DuplicateReadingError,
    Reading,
    ensure_unique_reading,
)

METER_ID = uuid4()


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
