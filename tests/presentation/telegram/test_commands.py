import pytest

from kommunalka.presentation.telegram.commands import BillCommand, UsageError, parse_bill_args


def test_a_month() -> None:
    assert parse_bill_args("2026-09") == BillCommand(2026, 9)


def test_no_arguments_ask_for_the_latest_bill() -> None:
    assert parse_bill_args(None) == BillCommand()
    assert parse_bill_args("  ") == BillCommand()


def test_a_month_and_a_household() -> None:
    assert parse_bill_args("2026-09 Дача ") == BillCommand(2026, 9, "Дача")


@pytest.mark.parametrize("args", ["2026-13", "2026-00", "Дача", "2026-9", "сентябрь 2026"])
def test_arguments_that_make_no_sense(args: str) -> None:
    with pytest.raises(UsageError):
        parse_bill_args(args)
