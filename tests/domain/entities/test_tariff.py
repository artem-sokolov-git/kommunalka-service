from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from kommunalka.domain import (
    DateRange,
    DomainError,
    OverlappingTariffPeriodError,
    TariffPeriod,
    ensure_no_overlap,
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
