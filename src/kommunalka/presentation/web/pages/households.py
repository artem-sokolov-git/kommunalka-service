"""The household list and the overview of one household."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.domain import Bill, DateRange, Household, MeteredBillLine, Service
from kommunalka.presentation.dependencies import TodayDep, UowDep
from kommunalka.presentation.web.formatting import (
    day_month,
    long_date,
    money,
    month_genitive,
    month_name,
    month_title,
    number,
    plural,
    service_kind,
    unit_label,
)
from kommunalka.presentation.web.pages.change import bill_change
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)


@dataclass(frozen=True, slots=True)
class ChartBar:
    year: int
    month: int
    label: str
    value: str
    title: str
    height: int
    latest: bool


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request, uow: UowDep) -> Response:
    households = queries.list_households(uow)
    if len(households) == 1:
        url = request.url_for("household_page", household_id=households[0].id)
        return RedirectResponse(str(url))
    return _households_page(request, households)


@router.get("/view/households", response_class=HTMLResponse)
def households_page(request: Request, uow: UowDep) -> HTMLResponse:
    return _households_page(request, queries.list_households(uow))


def _households_page(request: Request, households: list[Household]) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "home.html", {"title": "Коммуналка", "households": households}
    )


@router.get("/view/households/{household_id}", response_class=HTMLResponse)
def household_page(
    request: Request, household_id: UUID, uow: UowDep, today: TodayDep
) -> HTMLResponse:
    summary = queries.household_summary(uow, household_id)
    this_month = today.replace(day=1)
    next_month = (this_month + timedelta(days=32)).replace(day=1)
    meters = [item for item in summary.meters if item.meter.is_in_service_on(today)]
    taken = [
        item.last_reading.taken_on
        for item in meters
        if item.last_reading and item.last_reading.taken_on >= this_month
    ]
    if summary.unbilled:
        status = "unbilled"
    elif meters and len(taken) == len(meters):
        status = "done"
    else:
        status = "due"
    bills = summary.bills
    last, previous = (bills[-1] if bills else None), (bills[-2] if len(bills) > 1 else None)
    return templates.TemplateResponse(
        request,
        "household.html",
        {
            "title": summary.household.name,
            "household": summary.household,
            "section": "overview",
            "today": long_date(today),
            "status": status,
            "unbilled": [month_title(period.start) for period in summary.unbilled],
            "taken_on": day_month(max(taken)) if taken else "",
            "closed_month": month_name(DateRange.month_before(today).start.month),
            "next_window": f"с 1 по 5 {month_genitive(next_month.month)}",
            "days_left": plural((next_month - today).days, "день", "дня", "дней"),
            "last_bill": _bill_view(last, previous) if last else None,
            "breakdown": _breakdown(last, summary.services) if last else [],
            "chart": _chart(bills[-12:]),
            "year_total": _year_total(bills),
            "meters": [
                {
                    "label": item.meter.label,
                    "serial": item.meter.serial_number,
                    "kind": service_kind(item.service),
                    "value": number(item.last_reading.value) if item.last_reading else "—",
                    "unit": unit_label(item.service.unit),
                    "taken_on": day_month(item.last_reading.taken_on) if item.last_reading else "",
                }
                for item in meters
            ],
        },
    )


def _bill_view(bill: Bill, previous: Bill | None) -> dict[str, object]:
    month = bill.period_start.month
    return {
        "year": bill.period_start.year,
        "month": month,
        "title": month_name(month),
        "total": money(bill.total),
        "change": bill_change(bill, previous),
    }


def _breakdown(bill: Bill, services: Mapping[UUID, Service]) -> list[dict[str, object]]:
    lines: list[dict[str, object]] = []
    for line in bill.lines:
        service = services[line.service_id]
        quantity = (
            f"{number(line.quantity)} {unit_label(service.unit)}"
            if isinstance(line, MeteredBillLine)
            else ""
        )
        lines.append(
            {
                "kind": service_kind(service),
                "name": service.name,
                "quantity": quantity,
                "amount": money(line.amount),
                "share": f"{line.amount / bill.total * 100:.1f}" if bill.total else "0",
            }
        )
    return lines


def _chart(bills: Sequence[Bill]) -> list[ChartBar]:
    top = max((bill.total for bill in bills), default=Decimal(0))
    return [
        ChartBar(
            year=bill.period_start.year,
            month=bill.period_start.month,
            label=month_name(bill.period_start.month)[:3],
            value=f"{bill.total / 1000:.1f}".replace(".", ","),
            title=f"{month_title(bill.period_start)}: {money(bill.total)} грн",
            height=round(bill.total / top * 100) if top else 0,
            latest=index == len(bills) - 1,
        )
        for index, bill in enumerate(bills)
    ]


def _year_total(bills: Sequence[Bill]) -> dict[str, object] | None:
    if not bills:
        return None
    year = bills[-1].period_start.year
    same_year = [bill for bill in bills if bill.period_start.year == year]
    return {
        "year": year,
        "total": money(sum((bill.total for bill in same_year), Decimal(0))),
        "months": len(same_year),
    }
