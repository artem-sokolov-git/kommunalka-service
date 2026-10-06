from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from kommunalka.domain import (
    Bill,
    DateRange,
    DomainError,
    FixedBillLine,
    OverlappingTariffPeriodError,
    PeriodAlreadyBilledError,
    TariffPeriod,
    ensure_no_overlap,
    ensure_price_not_billed,
    next_tariff_period,
    revert_price_change,
)

SERVICE_ID = uuid4()


def make_tariff(
    valid_from: date, valid_to: date, service_id: UUID = SERVICE_ID, price: str = "1"
) -> TariffPeriod:
    return TariffPeriod(
        service_id=service_id, price=Decimal(price), valid_from=valid_from, valid_to=valid_to
    )


def test_rejects_negative_price() -> None:
    with pytest.raises(DomainError):
        make_tariff(date(2026, 1, 1), date(2026, 12, 31), price="-1")


def test_rejects_valid_to_before_valid_from() -> None:
    with pytest.raises(DomainError):
        make_tariff(date(2026, 12, 31), date(2026, 1, 1))


def test_covers_whole_billing_month_only() -> None:
    tariff = make_tariff(date(2026, 1, 1), date(2026, 9, 15))

    assert tariff.covers(DateRange.month_of(date(2026, 8, 1)))
    assert not tariff.covers(DateRange.month_of(date(2026, 9, 1)))


def test_periods_of_one_service_must_not_overlap() -> None:
    existing = make_tariff(date(2026, 1, 1), date(2026, 12, 31))

    ensure_no_overlap(existing, [existing])
    ensure_no_overlap(make_tariff(date(2027, 1, 1), date(2027, 12, 31)), [existing])
    ensure_no_overlap(
        make_tariff(date(2026, 6, 1), date(2027, 5, 31), service_id=uuid4()), [existing]
    )
    with pytest.raises(OverlappingTariffPeriodError):
        ensure_no_overlap(make_tariff(date(2026, 12, 31), date(2027, 12, 30)), [existing])


def test_open_ended_tariff_covers_any_later_month() -> None:
    tariff = TariffPeriod(service_id=SERVICE_ID, price=Decimal(1), valid_from=date(2024, 9, 1))

    assert tariff.covers(DateRange.month_of(date(2099, 12, 1)))
    assert not tariff.covers(DateRange.month_of(date(2024, 8, 1)))


def test_new_price_closes_the_open_period() -> None:
    current = TariffPeriod(
        service_id=SERVICE_ID, price=Decimal("7.96"), valid_from=date(2024, 9, 1)
    )

    closed, new = next_tariff_period(
        [current], service_id=SERVICE_ID, price=Decimal("8.50"), valid_from=date(2027, 1, 1)
    )

    assert closed is not None
    assert closed.id == current.id
    assert closed.valid_to == date(2026, 12, 31)
    assert (new.price, new.valid_from, new.valid_to) == (Decimal("8.50"), date(2027, 1, 1), None)


def test_first_price_closes_nothing() -> None:
    closed, new = next_tariff_period(
        [], service_id=SERVICE_ID, price=Decimal(1), valid_from=date(2027, 1, 1)
    )

    assert closed is None
    assert new.valid_from == date(2027, 1, 1)


@pytest.mark.parametrize(
    ("valid_from", "message"),
    [(date(2027, 1, 15), "first day of a month"), (date(2024, 9, 1), "must start after")],
)
def test_new_price_rules(valid_from: date, message: str) -> None:
    current = TariffPeriod(
        service_id=SERVICE_ID, price=Decimal("7.96"), valid_from=date(2024, 9, 1)
    )

    with pytest.raises(DomainError, match=message):
        next_tariff_period(
            [current], service_id=SERVICE_ID, price=Decimal(1), valid_from=valid_from
        )


def test_price_of_a_billed_month_cannot_change() -> None:
    september = Bill(
        household_id=uuid4(),
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        lines=(FixedBillLine(service_id=SERVICE_ID, amount=Decimal("300.78")),),
    )

    ensure_price_not_billed(SERVICE_ID, date(2026, 10, 1), [september])
    ensure_price_not_billed(uuid4(), date(2026, 9, 1), [september])
    with pytest.raises(PeriodAlreadyBilledError):
        ensure_price_not_billed(SERVICE_ID, date(2026, 9, 1), [september])


def test_undoing_a_price_reopens_the_one_before() -> None:
    before = make_tariff(date(2025, 12, 1), date(2026, 12, 31), price="300.78")
    latest = TariffPeriod(service_id=SERVICE_ID, price=Decimal(320), valid_from=date(2027, 1, 1))

    removed, reopened = revert_price_change([latest, before], service_id=SERVICE_ID)

    assert removed == latest
    assert reopened is not None
    assert (reopened.id, reopened.valid_to) == (before.id, None)


def test_undoing_a_price_after_a_gap_reopens_nothing() -> None:
    before = make_tariff(date(2025, 1, 1), date(2025, 6, 30))
    latest = TariffPeriod(service_id=SERVICE_ID, price=Decimal(2), valid_from=date(2026, 1, 1))

    assert revert_price_change([before, latest], service_id=SERVICE_ID) == (latest, None)


def test_nothing_to_undo_without_prices() -> None:
    with pytest.raises(DomainError, match="no price to undo"):
        revert_price_change([make_tariff(date(2025, 1, 1), date(2025, 6, 30))], service_id=uuid4())
