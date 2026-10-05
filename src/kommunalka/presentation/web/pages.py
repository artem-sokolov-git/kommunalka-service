"""HTML pages for people, on top of the same application queries as the JSON API."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse

from kommunalka.application import queries
from kommunalka.domain import Bill, FixedBillLine, Household, MeteredBillLine, Unit
from kommunalka.presentation.dependencies import UowDep
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)

MONTHS = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)  # fmt: skip
UNITS = {Unit.CUBIC_METER: "м³", Unit.KWH: "кВт·ч"}
NBSP = "\u00a0"


@dataclass(frozen=True, slots=True)
class BillSummary:
    year: int
    month: int
    title: str
    total: str


@dataclass(frozen=True, slots=True)
class HouseholdCard:
    household: Household
    bill_count: int
    last_bill: BillSummary | None


@dataclass(frozen=True, slots=True)
class YearView:
    year: int
    total: str
    bills: list[BillSummary]


@dataclass(frozen=True, slots=True)
class LineView:
    service: str
    readings: str
    quantity: str
    price: str
    amount: str


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request, uow: UowDep) -> HTMLResponse:
    households = [
        HouseholdCard(
            household=overview.household,
            bill_count=overview.bill_count,
            last_bill=_summary(overview.last_bill) if overview.last_bill else None,
        )
        for overview in queries.household_overviews(uow)
    ]
    return templates.TemplateResponse(
        request, "home.html", {"title": "Коммуналка", "households": households}
    )


@router.get("/view/households/{household_id}/bills", response_class=HTMLResponse)
def bills_page(request: Request, household_id: UUID, uow: UowDep) -> HTMLResponse:
    result = queries.household_bills(uow, household_id)
    by_year: dict[int, list[Bill]] = {}
    for bill in reversed(result.bills):
        by_year.setdefault(bill.period_start.year, []).append(bill)
    years = [
        YearView(
            year=year,
            total=_money(sum((bill.total for bill in bills), Decimal(0))),
            bills=[_summary(bill) for bill in bills],
        )
        for year, bills in by_year.items()
    ]
    return templates.TemplateResponse(
        request, "bills.html", {"title": "Счета", "household": result.household, "years": years}
    )


@router.get("/view/households/{household_id}/bills/{year}/{month}", response_class=HTMLResponse)
def bill_page(
    request: Request,
    household_id: UUID,
    year: int,
    month: Annotated[int, Path(ge=1, le=12)],
    uow: UowDep,
) -> HTMLResponse:
    details = queries.bill_details(uow, household_id, year, month)
    return templates.TemplateResponse(
        request,
        "bill.html",
        {
            "household": details.household,
            "title": f"Счёт за {MONTHS[month - 1]} {year}",
            "lines": [_line(line) for line in details.lines],
            "total": _money(details.bill.total),
            "previous": details.previous_period,
            "next": details.next_period,
        },
    )


def _line(details: queries.BillLineDetails) -> LineView:
    line, service = details.line, details.service
    match line:
        case FixedBillLine():
            return LineView(service.name, "", "", "", _money(line.amount))
        case MeteredBillLine():
            unit = UNITS[service.unit] if service.unit else ""
            return LineView(
                service=service.name,
                readings="; ".join(
                    f"{r.meter.label}: {_number(r.previous.value) if r.previous else '—'}"
                    f" → {_number(r.current.value)}"
                    for r in details.readings
                ),
                quantity=f"{_number(line.quantity)} {unit}",
                price=_money(line.price),
                amount=_money(line.amount),
            )


def _summary(bill: Bill) -> BillSummary:
    start: date = bill.period_start
    return BillSummary(start.year, start.month, MONTHS[start.month - 1], _money(bill.total))


def _number(value: Decimal) -> str:
    return f"{value:,f}".replace(",", NBSP).replace(".", ",")


def _money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", NBSP).replace(".", ",")
