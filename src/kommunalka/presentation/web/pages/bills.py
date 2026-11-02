"""The bills of a household: the list, one bill as a page and as a PDF, issuing a bill."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.application.exceptions import ApplicationError
from kommunalka.application.use_cases import issue_bill
from kommunalka.domain import Bill, DomainError, FixedBillLine, Household, MeteredBillLine
from kommunalka.presentation.dependencies import TodayDep, UowDep
from kommunalka.presentation.errors import describe_error
from kommunalka.presentation.web.bill_pdf import render_bill
from kommunalka.presentation.web.formatting import (
    InputError,
    money,
    month_name,
    month_title,
    number,
    parse_amounts,
    service_kind,
    signed_money,
    unit_label,
)
from kommunalka.presentation.web.messages import translate
from kommunalka.presentation.web.pages.change import Change, bill_change
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)


@dataclass(frozen=True, slots=True)
class BillSummary:
    year: int
    month: int
    title: str
    total: str


@dataclass(frozen=True, slots=True)
class YearView:
    year: int
    total: str
    bills: list[BillSummary]


@dataclass(frozen=True, slots=True)
class LineView:
    kind: str
    service: str
    readings: str
    quantity: str
    price: str
    amount: str
    change: str


@dataclass(frozen=True, slots=True)
class BillView:
    """A bill as the page and the PDF show it."""

    household: Household
    year: int
    month: int
    total: str
    change: Change | None
    lines: list[LineView]


@router.get("/view/households/{household_id}/bills", response_class=HTMLResponse)
def bills_page(request: Request, household_id: UUID, uow: UowDep) -> HTMLResponse:
    result = queries.household_bills(uow, household_id)
    by_year: dict[int, list[Bill]] = {}
    for bill in reversed(result.bills):
        by_year.setdefault(bill.period_start.year, []).append(bill)
    years = [
        YearView(
            year=year,
            total=money(sum((bill.total for bill in bills), Decimal(0))),
            bills=[_summary(bill) for bill in bills],
        )
        for year, bills in by_year.items()
    ]
    return templates.TemplateResponse(
        request,
        "bills.html",
        {
            "title": "Счета",
            "household": result.household,
            "section": "bills",
            "years": years,
        },
    )


@router.get("/view/households/{household_id}/bills/{year}/{month}", response_class=HTMLResponse)
def bill_page(
    request: Request,
    household_id: UUID,
    year: int,
    month: Annotated[int, Path(ge=1, le=12)],
    uow: UowDep,
    issued: bool = False,
) -> HTMLResponse:
    details = queries.bill_details(uow, household_id, year, month)
    bill, previous = details.bill, details.previous_bill
    view = _bill_view(details)
    return templates.TemplateResponse(
        request,
        "bill.html",
        {
            "household": details.household,
            "section": "bills",
            "title": f"Счёт за {month_name(month)} {year}",
            "heading": month_title(bill.period_start),
            "month_title": month_name(month),
            "year": year,
            "month": month,
            "lines": view.lines,
            "total": view.total,
            "change": view.change,
            "previous": previous.period_start if previous else None,
            "previous_title": month_name(previous.period_start.month) if previous else "",
            "next": details.next_period,
            "next_title": month_name(details.next_period.month) if details.next_period else "",
            "year_bills": [_summary(b) for b in reversed(details.year_bills)],
            "year_total": money(sum((b.total for b in details.year_bills), Decimal(0))),
            "issued": issued,
        },
    )


@router.get("/view/households/{household_id}/bills/{year}/{month}/pdf")
def bill_pdf(
    household_id: UUID,
    year: int,
    month: Annotated[int, Path(ge=1, le=12)],
    uow: UowDep,
    today: TodayDep,
) -> Response:
    view = _bill_view(queries.bill_details(uow, household_id, year, month))
    return Response(
        render_bill(view, today),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="kommunalka-{year}-{month:02d}.pdf"'},
    )


@router.post("/view/households/{household_id}/bills", response_class=HTMLResponse)
def issue_bill_form(
    request: Request,
    household_id: UUID,
    uow: UowDep,
    year: Annotated[int, Form()],
    month: Annotated[int, Form(ge=1, le=12)],
    fixed_service_id: Annotated[list[UUID] | None, Form()] = None,
    fixed_amount: Annotated[list[str] | None, Form()] = None,
) -> Response:
    try:
        fixed_amounts = parse_amounts(
            dict(zip(fixed_service_id or [], fixed_amount or [], strict=True))
        )
        issue_bill(
            uow, household_id=household_id, year=year, month=month, fixed_amounts=fixed_amounts
        )
    except (DomainError, ApplicationError, InputError) as error:
        message = (
            str(error) if isinstance(error, InputError) else translate(describe_error(error)[1])
        )
        # Back to the readings page, so reloading it doesn't post the form again.
        url = request.url_for("readings_page", household_id=household_id)
        return RedirectResponse(f"{url}?{urlencode({'error': message})}", status_code=303)
    url = request.url_for("bill_page", household_id=household_id, year=year, month=month)
    return RedirectResponse(f"{url}?issued=1", status_code=303)


def _bill_view(details: queries.BillDetails) -> BillView:
    bill, previous = details.bill, details.previous_bill
    previous_amounts = {line.service_id: line.amount for line in previous.lines} if previous else {}
    return BillView(
        household=details.household,
        year=bill.period_start.year,
        month=bill.period_start.month,
        total=money(bill.total),
        change=bill_change(bill, previous),
        lines=[_line(line, previous_amounts) for line in details.lines],
    )


def _line(details: queries.BillLineDetails, previous_amounts: Mapping[UUID, Decimal]) -> LineView:
    line, service = details.line, details.service
    before = previous_amounts.get(line.service_id)
    if before is None:
        change = ""
    elif line.amount == before:
        change = "без изменений"
    else:
        change = signed_money(line.amount - before)
    match line:
        case FixedBillLine():
            kind = service_kind(service)
            return LineView(kind, service.name, "", "", "", money(line.amount), change)
        case MeteredBillLine():
            return LineView(
                kind=service_kind(service),
                service=service.name,
                readings="; ".join(
                    (f"{r.meter.label}: " if len(details.readings) > 1 else "")
                    + f"{number(r.previous.value) if r.previous else '—'}"
                    f" → {number(r.current.value)}"
                    for r in details.readings
                ),
                quantity=f"{number(line.quantity)} {unit_label(service.unit)}",
                price=money(line.price),
                amount=money(line.amount),
                change=change,
            )


def _summary(bill: Bill) -> BillSummary:
    start: date = bill.period_start
    return BillSummary(start.year, start.month, month_name(start.month), money(bill.total))
