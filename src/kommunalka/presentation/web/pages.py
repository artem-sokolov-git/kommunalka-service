"""HTML pages for people, on top of the same application queries as the JSON API."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.application.exceptions import ApplicationError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import (
    change_price,
    correct_reading,
    issue_bill,
    submit_readings,
)
from kommunalka.domain import (
    Bill,
    DateRange,
    DomainError,
    FixedBillLine,
    Household,
    MeteredBillLine,
)
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
            "previous_title": _month_title(details.previous_period),
            "next": details.next_period,
            "next_title": _month_title(details.next_period),
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


def _month_title(start: date | None) -> str:
    return f"{month_name(start.month)} {start.year}" if start else ""


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
    error: str | None = None,
) -> HTMLResponse:
    return _readings_page(
        request, uow, household_id, taken_on or today, today, saved=saved, error=error
    )


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
        values = _parse_values(uow, household_id, taken_on, entered)
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
            today,
            entered=entered,
            error=translate(detail),
            code=code,
        )
    except InputError as error:
        return _readings_page(
            request,
            uow,
            household_id,
            taken_on,
            today,
            entered=entered,
            error=str(error),
            code=422,
        )
    url = request.url_for("readings_page", household_id=household_id)
    return RedirectResponse(f"{url}?saved=1&taken_on={taken_on}", status_code=303)


def _parse_values(
    uow: UnitOfWork, household_id: UUID, taken_on: date, entered: Mapping[UUID, str]
) -> dict[UUID, Decimal]:
    values = {}
    for meter_id, text in entered.items():
        if not text.strip():
            continue
        try:
            values[meter_id] = parse_number(text)
        except InputError as error:
            labels = {
                item.meter.id: item.meter.label
                for item in queries.reading_form(uow, household_id, taken_on).meters
            }
            raise InputError(f"{labels.get(meter_id, 'Счётчик')}: {error}") from None
    return values


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
        fixed_amounts = {
            service_id: parse_number(amount)
            for service_id, amount in zip(fixed_service_id or [], fixed_amount or [], strict=True)
            if amount.strip()
        }
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
    return RedirectResponse(str(url), status_code=303)


def _readings_page(
    request: Request,
    uow: UnitOfWork,
    household_id: UUID,
    taken_on: date,
    today: date,
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
            "today": today,
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
                {
                    "period": month.period,
                    "title": _month_title(month.period.start),
                    "charges": [
                        {
                            "service_id": charge.service.id,
                            "name": charge.service.name,
                            "amount": "" if charge.amount is None else number(charge.amount),
                        }
                        for charge in month.fixed_charges
                    ],
                }
                for month in form.unbilled
            ],
            "last_billed": form.last_billed_period,
            "last_billed_title": _month_title(
                form.last_billed_period.start if form.last_billed_period else None
            ),
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


@router.get("/view/tariffs", response_class=HTMLResponse)
def tariffs_page(
    request: Request,
    uow: UowDep,
    today: TodayDep,
    saved: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    return templates.TemplateResponse(
        request,
        "tariffs.html",
        {
            "title": "Тарифы",
            "services": [
                {
                    "id": item.service.id,
                    "name": item.service.name,
                    "per": f"за {unit_label(item.service.unit)}"
                    if item.service.unit
                    else "в месяц",
                    "periods": [
                        {
                            "from": period.valid_from.strftime("%d.%m.%Y"),
                            "to": period.valid_to.strftime("%d.%m.%Y") if period.valid_to else "",
                            "price": money(period.price),
                            "current": period.covers(DateRange.month_of(today)),
                        }
                        for period in item.periods
                    ],
                }
                for item in queries.tariff_overview(uow)
            ],
            "next_month": f"{next_month:%Y-%m}",
            "saved": saved,
            "error": error,
        },
    )


@router.post("/view/tariffs/{service_id}", response_class=HTMLResponse)
def change_price_form(
    request: Request,
    service_id: UUID,
    uow: UowDep,
    price: Annotated[str, Form()],
    month: Annotated[str, Form()],
) -> Response:
    url = request.url_for("tariffs_page")
    try:
        valid_from = _parse_month(month)
        change_price(uow, service_id=service_id, price=parse_number(price), valid_from=valid_from)
    except InputError as error:
        return RedirectResponse(f"{url}?{urlencode({'error': str(error)})}", status_code=303)
    except (DomainError, ApplicationError) as error:
        message = translate(describe_error(error)[1])
        return RedirectResponse(f"{url}?{urlencode({'error': message})}", status_code=303)
    return RedirectResponse(f"{url}?saved=1", status_code=303)


def _parse_month(text: str) -> date:
    try:
        return date.fromisoformat(f"{text}-01")
    except ValueError:
        raise InputError(f"не месяц «{text}»") from None
