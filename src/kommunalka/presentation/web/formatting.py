"""How numbers, months and units are written for people (Russian)."""

from decimal import Decimal, InvalidOperation

from kommunalka.domain import Unit

MONTHS = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)  # fmt: skip
UNITS = {Unit.CUBIC_METER: "м³", Unit.KWH: "кВт·ч"}
NBSP = "\u00a0"


class InputError(Exception):
    """A form value that can't be parsed."""


def month_name(month: int) -> str:
    return MONTHS[month - 1]


def unit_label(unit: Unit | None) -> str:
    return UNITS[unit] if unit else ""


def number(value: Decimal) -> str:
    return f"{value:,f}".replace(",", NBSP).replace(".", ",")


def money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", NBSP).replace(".", ",")


def parse_number(text: str) -> Decimal:
    """Parse a number as people type it: `41 768`, `41768,5`."""
    cleaned = text.replace(" ", "").replace(NBSP, "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise InputError(f"Не число: {text!r}") from None
