"""How numbers, months and units are written for people (Russian)."""

from datetime import date
from decimal import Decimal, InvalidOperation

from kommunalka.domain import Unit

MONTHS = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)  # fmt: skip
MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)  # fmt: skip
MONTHS_PREPOSITIONAL = (
    "январе", "феврале", "марте", "апреле", "мае", "июне",
    "июле", "августе", "сентябре", "октябре", "ноябре", "декабре",
)  # fmt: skip
UNITS = {Unit.CUBIC_METER: "м³", Unit.KWH: "кВт·ч"}
NBSP = "\u00a0"
MINUS = "\u2212"


class InputError(Exception):
    """A form value that can't be parsed."""


def month_name(month: int) -> str:
    return MONTHS[month - 1]


def month_genitive(month: int) -> str:
    return MONTHS_GENITIVE[month - 1]


def day_month(day: date) -> str:
    """`1 октября`."""
    return f"{day.day}{NBSP}{month_genitive(day.month)}"


def long_date(day: date) -> str:
    """`1 октября 2026`."""
    return f"{day_month(day)} {day.year}"


def in_month(month: int) -> str:
    """`в августе`."""
    return f"в {MONTHS_PREPOSITIONAL[month - 1]}"


def plural(count: int, one: str, few: str, many: str) -> str:
    """`1 день`, `3 дня`, `26 дней`."""
    if count % 10 == 1 and count % 100 != 11:
        word = one
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        word = few
    else:
        word = many
    return f"{count}{NBSP}{word}"


def unit_label(unit: Unit | None) -> str:
    return UNITS[unit] if unit else ""


def number(value: Decimal) -> str:
    return f"{value:,f}".replace(",", NBSP).replace(".", ",")


def money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", NBSP).replace(".", ",")


def signed_money(value: Decimal) -> str:
    sign = "+" if value > 0 else MINUS if value < 0 else ""
    return sign + money(abs(value))


def parse_number(text: str) -> Decimal:
    """Parse a number as people type it: `41 768`, `41768,5`."""
    cleaned = text.replace(" ", "").replace(NBSP, "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise InputError(f"не число «{text}»") from None
