"""HTML pages for people, on top of the same application queries as the JSON API."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.application.exceptions import ApplicationError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import correct_reading, issue_bill, submit_readings
from kommunalka.domain import Bill, DomainError, FixedBillLine, Household, MeteredBillLine
from kommunalka.presentation.dependencies import TodayDep, UowDep
from kommunalka.presentation.errors import describe_error
from kommunalka.presentation.web.formatting import (
    InputError,
    money,
    month_name,
    number,
    parse_number,
    unit_label,
)
from kommunalka.presentation.web.messages import translate
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)


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
            total=money(sum((bill.total for bill in bills), Decimal(0))),
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
            "title": f"Счёт за {month_name(month)} {year}",
            "lines": [_line(line) for line in details.lines],
            "total": money(details.bill.total),
            "previous": details.previous_period,
            "next": details.next_period,
        },
    )


def _line(details: queries.BillLineDetails) -> LineView:
    line, service = details.line, details.service
    match line:
        case FixedBillLine():
            return LineView(service.name, "", "", "", money(line.amount))
        case MeteredBillLine():
            unit = unit_label(service.unit)
            return LineView(
                service=service.name,
                readings="; ".join(
                    f"{r.meter.label}: {number(r.previous.value) if r.previous else '—'}"
                    f" → {number(r.current.value)}"
                    for r in details.readings
                ),
                quantity=f"{number(line.quantity)} {unit}",
                price=money(line.price),
                amount=money(line.amount),
            )


def _summary(bill: Bill) -> BillSummary:
    start: date = bill.period_start
    return BillSummary(start.year, start.month, month_name(start.month), money(bill.total))


@router.get("/view/households/{household_id}/readings", response_class=HTMLResponse)
def readings_page(
    request: Request,
    household_id: UUID,
    uow: UowDep,
    today: TodayDep,
    taken_on: date | None = None,
    saved: bool = False,
) -> HTMLResponse:
    return _readings_page(request, uow, household_id, taken_on or today, saved=saved)


@router.post("/view/households/{household_id}/readings", response_class=HTMLResponse)
def submit_readings_form(
    request: Request,
    household_id: UUID,
    uow: UowDep,
    today: TodayDep,
    taken_on: Annotated[date, Form()],
    meter_id: Annotated[list[UUID], Form()],
    value: Annotated[list[str], Form()],
) -> Response:
    entered = dict(zip(meter_id, value, strict=True))
    try:
        values = {m: parse_number(v) for m, v in entered.items() if v.strip()}
        if not values:
            raise InputError("Введите хотя бы одно показание")
        submit_readings(
            uow, household_id=household_id, taken_on=taken_on, values=values, today=today
        )
    except (DomainError, ApplicationError) as error:
        code, detail = describe_error(error)
        return _readings_page(
            request,
            uow,
            household_id,
            taken_on,
            entered=entered,
            error=translate(detail),
            code=code,
        )
    except InputError as error:
        return _readings_page(
            request, uow, household_id, taken_on, entered=entered, error=str(error), code=422
        )
    url = request.url_for("readings_page", household_id=household_id)
    return RedirectResponse(f"{url}?saved=1&taken_on={taken_on}", status_code=303)


@router.post("/view/households/{household_id}/bills", response_class=HTMLResponse)
def issue_bill_form(
    request: Request,
    household_id: UUID,
    uow: UowDep,
    year: Annotated[int, Form()],
    month: Annotated[int, Form(ge=1, le=12)],
    taken_on: Annotated[date, Form()],
) -> Response:
    try:
        issue_bill(uow, household_id=household_id, year=year, month=month, fixed_amounts={})
    except (DomainError, ApplicationError) as error:
        code, detail = describe_error(error)
        return _readings_page(
            request, uow, household_id, taken_on, error=translate(detail), code=code
        )
    url = request.url_for("bill_page", household_id=household_id, year=year, month=month)
    return RedirectResponse(str(url), status_code=303)


def _readings_page(
    request: Request,
    uow: UnitOfWork,
    household_id: UUID,
    taken_on: date,
    *,
    saved: bool = False,
    entered: Mapping[UUID, str] | None = None,
    error: str | None = None,
    code: int = 200,
) -> HTMLResponse:
    form = queries.reading_form(uow, household_id, taken_on)
    return templates.TemplateResponse(
        request,
        "readings.html",
        {
            "title": "Показания",
            "household": form.household,
            "taken_on": taken_on,
            "meters": [
                {
                    "id": item.meter.id,
                    "label": item.meter.label,
                    "service": item.service.name,
                    "last": item.last_reading,
                    "last_value": number(item.last_reading.value) if item.last_reading else "",
                    "unit": unit_label(item.service.unit),
                    "entered": (entered or {}).get(item.meter.id, ""),
                    "correctable": item.last_reading_correctable,
                }
                for item in form.meters
            ],
            "unbilled": [
                (period, f"{month_name(period.start.month)} {period.start.year}")
                for period in form.unbilled_periods
            ],
            "last_billed": form.last_billed_period,
            "saved": saved,
            "error": error,
        },
        status_code=code,
    )


@router.get("/view/households/{household_id}/readings/{reading_id}", response_class=HTMLResponse)
def correction_page(
    request: Request, household_id: UUID, reading_id: UUID, uow: UowDep
) -> HTMLResponse:
    return _correction_page(request, uow, household_id, reading_id)


@router.post("/view/households/{household_id}/readings/{reading_id}", response_class=HTMLResponse)
def correct_reading_form(
    request: Request,
    household_id: UUID,
    reading_id: UUID,
    uow: UowDep,
    value: Annotated[str, Form()],
) -> Response:
    queries.reading_correction(uow, household_id, reading_id)
    try:
        correct_reading(uow, reading_id=reading_id, value=parse_number(value))
    except (DomainError, ApplicationError) as error:
        code, detail = describe_error(error)
        return _correction_page(
            request,
            uow,
            household_id,
            reading_id,
            entered=value,
            error=translate(detail),
            code=code,
        )
    except InputError as error:
        return _correction_page(
            request, uow, household_id, reading_id, entered=value, error=str(error), code=422
        )
    url = request.url_for("readings_page", household_id=household_id)
    return RedirectResponse(f"{url}?saved=1", status_code=303)


def _correction_page(
    request: Request,
    uow: UnitOfWork,
    household_id: UUID,
    reading_id: UUID,
    *,
    entered: str | None = None,
    error: str | None = None,
    code: int = 200,
) -> HTMLResponse:
    correction = queries.reading_correction(uow, household_id, reading_id)
    reading, previous = correction.reading, correction.previous
    return templates.TemplateResponse(
        request,
        "correct_reading.html",
        {
            "title": "Исправить показание",
            "household": correction.household,
            "meter": correction.meter,
            "reading": reading,
            "value": entered if entered is not None else number(reading.value),
            "previous": previous,
            "previous_value": number(previous.value) if previous else "",
            "error": error,
        },
        status_code=code,
    )
