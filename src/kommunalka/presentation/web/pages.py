"""HTML pages for people, on top of the same application queries as the JSON API."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.application.exceptions import ApplicationError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import issue_bill, submit_readings
from kommunalka.domain import Bill, DomainError, FixedBillLine, Household, MeteredBillLine, Unit
from kommunalka.presentation.dependencies import UowDep
from kommunalka.presentation.errors import describe_error
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)


class InputError(Exception):
    """A form value that can't be parsed."""


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


@router.get("/view/households/{household_id}/readings", response_class=HTMLResponse)
def readings_page(
    request: Request,
    household_id: UUID,
    uow: UowDep,
    taken_on: date | None = None,
    saved: bool = False,
) -> HTMLResponse:
    return _readings_page(request, uow, household_id, taken_on or date.today(), saved=saved)


@router.post("/view/households/{household_id}/readings", response_class=HTMLResponse)
def submit_readings_form(
    request: Request,
    household_id: UUID,
    uow: UowDep,
    taken_on: Annotated[date, Form()],
    meter_id: Annotated[list[UUID], Form()],
    value: Annotated[list[str], Form()],
) -> Response:
    entered = dict(zip(meter_id, value, strict=True))
    try:
        values = {m: _parse_number(v) for m, v in entered.items() if v.strip()}
        if not values:
            raise InputError("Введите хотя бы одно показание")
        submit_readings(uow, household_id=household_id, taken_on=taken_on, values=values)
    except (DomainError, ApplicationError) as error:
        code, detail = describe_error(error)
        return _readings_page(
            request, uow, household_id, taken_on, entered=entered, error=detail, code=code
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
        return _readings_page(request, uow, household_id, taken_on, error=detail, code=code)
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
    period = form.billing_period
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
                    "last_value": _number(item.last_reading.value) if item.last_reading else "",
                    "unit": UNITS[item.service.unit] if item.service.unit else "",
                    "entered": (entered or {}).get(item.meter.id, ""),
                }
                for item in form.meters
            ],
            "period": period,
            "period_title": f"{MONTHS[period.start.month - 1]} {period.start.year}",
            "bill_issued": form.bill_issued,
            "saved": saved,
            "error": error,
        },
        status_code=code,
    )


def _parse_number(text: str) -> Decimal:
    """Parse a number as people type it: `41 768`, `41768,5`."""
    cleaned = text.replace(" ", "").replace(NBSP, "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise InputError(f"Не число: {text!r}") from None
