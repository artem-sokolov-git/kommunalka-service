"""How a bill total differs from the previous bill, as the overview and the bill page show it."""

from dataclasses import dataclass
from typing import Literal

from kommunalka.domain import Bill
from kommunalka.presentation.web.formatting import in_month, money


@dataclass(frozen=True, slots=True)
class Change:
    text: str
    direction: Literal["up", "down", "same"]


def bill_change(bill: Bill, previous: Bill | None) -> Change | None:
    if previous is None:
        return None
    diff = bill.total - previous.total
    where = in_month(previous.period_start.month)
    if diff == 0:
        return Change(f"столько же, сколько {where}", "same")
    word = "больше" if diff > 0 else "меньше"
    return Change(f"на {money(abs(diff))} {word}, чем {where}", "up" if diff > 0 else "down")
