"""Parsing of the bot's command arguments: text in, a command object out; no database."""

import re
from dataclasses import dataclass

BILL_ARGS = re.compile(r"(?:(\d{4})-(\d{2})(?:\s+(.+))?)?")


class UsageError(ValueError):
    """The arguments of a known command make no sense."""


@dataclass(frozen=True)
class BillCommand:
    """`/bill [YYYY-MM [household]]`: no period means the latest bill."""

    year: int | None = None
    month: int | None = None
    household: str | None = None


def parse_bill_args(args: str | None) -> BillCommand:
    match = BILL_ARGS.fullmatch((args or "").strip())
    if not match:
        raise UsageError(f"unexpected arguments {args!r}")
    year, month, household = match.groups()
    if month is not None and not 1 <= int(month) <= 12:
        raise UsageError(f"month {month} is out of range")
    return BillCommand(
        year=int(year) if year else None,
        month=int(month) if month else None,
        household=household,
    )
