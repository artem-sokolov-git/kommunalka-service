from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from kommunalka.domain import DateRange, DomainError, FixedBillLine, MeteredBillLine


def test_date_range_rejects_end_before_start() -> None:
    with pytest.raises(DomainError):
        DateRange(date(2026, 2, 1), date(2026, 1, 31))


def test_date_range_contains_both_bounds() -> None:
    period = DateRange(date(2026, 9, 1), date(2026, 9, 30))

    assert period.contains(date(2026, 9, 1))
    assert period.contains(date(2026, 9, 30))
    assert not period.contains(date(2026, 10, 1))


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (DateRange(date(2026, 9, 30), date(2026, 10, 31)), True),
        (DateRange(date(2026, 10, 1), date(2026, 10, 31)), False),
    ],
)
def test_date_range_overlaps(other: DateRange, expected: bool) -> None:
    assert DateRange(date(2026, 9, 1), date(2026, 9, 30)).overlaps(other) is expected


def test_month_of_handles_leap_year() -> None:
    assert DateRange.month_of(date(2024, 2, 10)) == DateRange(date(2024, 2, 1), date(2024, 2, 29))


def test_month_before_crosses_year() -> None:
    assert DateRange.month_before(date(2026, 1, 4)) == DateRange(
        date(2025, 12, 1), date(2025, 12, 31)
    )


def test_metered_line_amount_is_rounded_to_kopecks() -> None:
    line = MeteredBillLine(service_id=uuid4(), quantity=Decimal("123.456"), price=Decimal("6.43"))

    assert line.amount == Decimal("793.82")


@pytest.mark.parametrize(("quantity", "price"), [("-1", "1"), ("1", "-1")])
def test_metered_line_rejects_negative_values(quantity: str, price: str) -> None:
    with pytest.raises(DomainError):
        MeteredBillLine(service_id=uuid4(), quantity=Decimal(quantity), price=Decimal(price))


def test_fixed_line_rejects_negative_amount() -> None:
    with pytest.raises(DomainError):
        FixedBillLine(service_id=uuid4(), amount=Decimal("-0.01"))
