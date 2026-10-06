"""Russian texts for error messages that reach the pages.

The domain and application raise English messages, shared with the JSON API. A message
without a translation is shown as is.
"""

import re
from collections.abc import Callable
from datetime import date

from kommunalka.presentation.web.formatting import month_name

MONTH = r"(\d{4})-(\d{2})"
DAY = r"(\d{4}-\d{2}-\d{2})"
LABEL = r"'([^']*)'"


def _month(match: re.Match[str], group: int = 1) -> str:
    return f"{month_name(int(match[group + 1]))} {match[group]}"


def _day(match: re.Match[str], group: int = 1) -> str:
    return f"{date.fromisoformat(match[group]):%d.%m.%Y}"


TRANSLATIONS: list[tuple[str, Callable[[re.Match[str]], str]]] = [
    (r"Reading value decreased", lambda m: "показание меньше предыдущего"),
    (r"Reading value must not be negative", lambda m: "показание не может быть отрицательным"),
    (
        rf"Reading must be taken after the last one on {DAY}",
        lambda m: f"дата должна быть позже последнего показания ({_day(m)})",
    ),
    (
        rf"Reading date {DAY} is in the future",
        lambda m: f"дата показания {_day(m)} ещё не наступила",
    ),
    (rf"Reading for {MONTH} already exists", lambda m: f"показание за {_month(m)} уже подано"),
    (
        rf"Meter {LABEL} is not in service on {DAY}",
        lambda m: f"счётчик «{m[1]}» не работает на {_day(m, 2)}",
    ),
    (
        rf"Meter {LABEL} belongs to another household",
        lambda m: f"счётчик «{m[1]}» из другого домохозяйства",
    ),
    (
        rf"Meter {LABEL} has no reading for {MONTH}",
        lambda m: f"нет показания счётчика «{m[1]}» за {_month(m, 2)}",
    ),
    (
        rf"Meter {LABEL} has no reading on {DAY}",
        lambda m: f"нет показания счётчика «{m[1]}» от {_day(m, 2)}",
    ),
    (
        rf"{MONTH} is already billed",
        lambda m: f"счёт за {_month(m)} уже выставлен, показания этого месяца менять нельзя",
    ),
    (
        rf"Bill for {MONTH} already uses the current price",
        lambda m: f"счёт за {_month(m)} уже выставлен по текущей цене",
    ),
    (
        rf"A new price must start after {DAY}",
        lambda m: f"новая цена должна начинаться позже {_day(m)}",
    ),
    (r"Tariff price must not be negative", lambda m: "цена не может быть отрицательной"),
    (r"Service has no price to undo", lambda m: "у услуги нет цены, которую можно отменить"),
    (rf"Bill for {MONTH} already exists", lambda m: f"счёт за {_month(m)} уже выставлен"),
    (rf"Bill for {MONTH} not found", lambda m: f"счёт за {_month(m)} не найден"),
    (rf"No tariff for service \S+ in {MONTH}", lambda m: f"нет тарифа на {_month(m)}"),
    (r"\w+ [0-9a-f-]{36} not found", lambda m: "не найдено"),
    (r"Conflicts with existing data", lambda m: "конфликт с уже сохранёнными данными"),
    (r"Not Found", lambda m: "страница не найдена"),
]


def translate(message: str) -> str:
    for pattern, text in TRANSLATIONS:
        message = re.sub(pattern, text, message)
    return message[:1].upper() + message[1:]
