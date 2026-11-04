"""Russian texts of the bot's replies."""

USAGE = "Формат: /bill 2026-09 — счёт за месяц; /bill — последний счёт."
NO_HOUSEHOLD = "Домохозяйство не найдено."
NO_BILLS = "Счетов пока нет."


def several_households(names: list[str]) -> str:
    return (
        f"Домохозяйств несколько, добавьте название: /bill 2026-09 Название ({', '.join(names)})."
    )


def caption(month_name: str, year: int, household: str) -> str:
    return f"Счёт за {month_name} {year} · {household}"
