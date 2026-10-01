from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from kommunalka.domain import (
    Bill,
    BillLine,
    DateRange,
    DomainError,
    DuplicateBillError,
    FixedBillLine,
    MeteredBillLine,
    PeriodAlreadyBilledError,
    ensure_not_billed,
    ensure_unique_bill,
)

HOUSEHOLD_ID = uuid4()
SEPTEMBER = DateRange.month_of(date(2026, 9, 1))


def make_bill(
    lines: tuple[BillLine, ...] = (),
    period: DateRange = SEPTEMBER,
    household_id: UUID = HOUSEHOLD_ID,
) -> Bill:
    return Bill(
        household_id=household_id,
        period_start=period.start,
        period_end=period.end,
        lines=lines,
    )


def test_total_sums_lines() -> None:
    bill = make_bill(
        (
            MeteredBillLine(service_id=uuid4(), quantity=Decimal("42.5"), price=Decimal("0.78")),
            FixedBillLine(service_id=uuid4(), amount=Decimal("12.30")),
        )
    )

    assert bill.total == Decimal("45.45")


def test_empty_bill_total_is_zero() -> None:
    assert make_bill().total == Decimal("0.00")


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 9, 1), date(2026, 9, 29)),
        (date(2026, 9, 2), date(2026, 9, 30)),
        (date(2026, 9, 1), date(2026, 10, 31)),
        (date(2026, 9, 30), date(2026, 9, 1)),
    ],
)
def test_period_must_be_whole_month(start: date, end: date) -> None:
    with pytest.raises(DomainError):
        Bill(household_id=HOUSEHOLD_ID, period_start=start, period_end=end, lines=())


def test_rejects_two_lines_of_one_service() -> None:
    service_id = uuid4()

    with pytest.raises(DomainError):
        make_bill(
            (
                FixedBillLine(service_id=service_id, amount=Decimal(1)),
                FixedBillLine(service_id=service_id, amount=Decimal(2)),
            )
        )


def test_one_bill_per_household_and_month() -> None:
    existing = make_bill()

    ensure_unique_bill(existing, [existing])
    ensure_unique_bill(make_bill(household_id=uuid4()), [existing])
    ensure_unique_bill(make_bill(period=DateRange.month_of(date(2026, 10, 1))), [existing])
    with pytest.raises(DuplicateBillError):
        ensure_unique_bill(make_bill(), [existing])


def test_billed_month_is_frozen() -> None:
    bills = [make_bill()]

    ensure_not_billed(HOUSEHOLD_ID, DateRange.month_of(date(2026, 10, 1)), bills)
    ensure_not_billed(uuid4(), SEPTEMBER, bills)
    with pytest.raises(PeriodAlreadyBilledError):
        ensure_not_billed(HOUSEHOLD_ID, SEPTEMBER, bills)
