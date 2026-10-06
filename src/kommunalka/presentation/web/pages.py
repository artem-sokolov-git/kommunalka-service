"""HTML pages for people, on top of the same application queries as the JSON API."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal
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
    submit_readings_and_issue_bill,
    undo_price_change,
)
from kommunalka.domain import (
    Bill,
    DateRange,
    DomainError,
    FixedBillLine,
    Household,
    MeteredBillLine,
    Service,
    TariffPeriod,
    Unit,
)
from kommunalka.presentation.dependencies import TodayDep, UowDep
from kommunalka.presentation.errors import describe_error
from kommunalka.presentation.web.formatting import (
    InputError,
    day_month,
    in_month,
    long_date,
    money,
    month_genitive,
    month_name,
    number,
    parse_number,
    plural,
    signed_money,
    unit_label,
)
from kommunalka.presentation.web.messages import translate
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)

KINDS = {Unit.CUBIC_METER: "gas", Unit.KWH: "power"}


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
    kind: str
    service: str
    readings: str
    quantity: str
    price: str
    amount: str
    change: str


@dataclass(frozen=True, slots=True)
class Change:
    """How a bill total differs from the previous bill."""

    text: str
    direction: Literal["up", "down", "same"]


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
    overviews = queries.household_overviews(uow)
    if len(overviews) == 1:
        url = request.url_for("household_page", household_id=overviews[0].household.id)
        return RedirectResponse(str(url))
    households = [
        HouseholdCard(
            household=overview.household,
            bill_count=overview.bill_count,
            last_bill=_summary(overview.last_bill) if overview.last_bill else None,
        )
        for overview in overviews
    ]
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
            "unbilled": [_month_title(period.start) for period in summary.unbilled],
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
                    "kind": _kind(item.service),
                    "value": number(item.last_reading.value) if item.last_reading else "—",
                    "unit": unit_label(item.service.unit),
                    "taken_on": day_month(item.last_reading.taken_on) if item.last_reading else "",
                }
                for item in meters
            ],
        },
    )


def _kind(service: Service) -> str:
    return KINDS[service.unit] if service.unit else "fixed"


def _bill_view(bill: Bill, previous: Bill | None) -> dict[str, object]:
    month = bill.period_start.month
    return {
        "year": bill.period_start.year,
        "month": month,
        "title": month_name(month),
        "total": money(bill.total),
        "change": _change(bill, previous),
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
                "kind": _kind(service),
                "name": service.name,
                "quantity": quantity,
                "amount": money(line.amount),
                "share": f"{line.amount / bill.total * 100:.1f}" if bill.total else "0",
            }
        )
    return lines


def _change(bill: Bill, previous: Bill | None) -> Change | None:
    if previous is None:
        return None
    diff = bill.total - previous.total
    where = in_month(previous.period_start.month)
    if diff == 0:
        return Change(f"столько же, сколько {where}", "same")
    word = "больше" if diff > 0 else "меньше"
    return Change(f"на {money(abs(diff))} {word}, чем {where}", "up" if diff > 0 else "down")


def _chart(bills: Sequence[Bill]) -> list[ChartBar]:
    top = max((bill.total for bill in bills), default=Decimal(0))
    return [
        ChartBar(
            year=bill.period_start.year,
            month=bill.period_start.month,
            label=month_name(bill.period_start.month)[:3],
            value=f"{bill.total / 1000:.1f}".replace(".", ","),
            title=f"{_month_title(bill.period_start)}: {money(bill.total)} грн",
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
    previous_amounts = {line.service_id: line.amount for line in previous.lines} if previous else {}
    lines = [_line(line, bill, previous_amounts) for line in details.lines]
    change = _change(bill, previous)
    return templates.TemplateResponse(
        request,
        "bill.html",
        {
            "household": details.household,
            "section": "bills",
            "title": f"Счёт за {month_name(month)} {year}",
            "heading": _month_title(bill.period_start),
            "month_title": month_name(month),
            "year": year,
            "month": month,
            "lines": lines,
            "total": money(bill.total),
            "change": change,
            "card": {
                "file": f"kommunalka-{year}-{month:02d}.png",
                "household": details.household.name,
                "month": month_name(month),
                "year": year,
                "total": money(bill.total),
                "change": {"text": change.text, "direction": change.direction} if change else None,
                "lines": [
                    {
                        "kind": line.kind,
                        "name": line.service,
                        "readings": line.readings,
                        "quantity": line.quantity,
                        "price": line.price,
                        "amount": line.amount,
                    }
                    for line in lines
                ],
            },
            "previous": previous.period_start if previous else None,
            "previous_title": month_name(previous.period_start.month) if previous else "",
            "next": details.next_period,
            "next_title": month_name(details.next_period.month) if details.next_period else "",
            "year_bills": [_summary(b) for b in reversed(details.year_bills)],
            "year_total": money(sum((b.total for b in details.year_bills), Decimal(0))),
            "issued": issued,
        },
    )


def _line(
    details: queries.BillLineDetails, bill: Bill, previous_amounts: Mapping[UUID, Decimal]
) -> LineView:
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
            return LineView(_kind(service), service.name, "", "", "", money(line.amount), change)
        case MeteredBillLine():
            return LineView(
                kind=_kind(service),
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
    corrected: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    return _readings_page(
        request,
        uow,
        household_id,
        taken_on or today,
        today,
        notice="Показание исправлено." if corrected else "Показания сохранены." if saved else "",
        error=error,
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
    action: Annotated[Literal["save", "issue"], Form()] = "save",
    fixed_service_id: Annotated[list[UUID] | None, Form()] = None,
    fixed_amount: Annotated[list[str] | None, Form()] = None,
) -> Response:
    entered = dict(zip(meter_id, value, strict=True))
    fixed = dict(zip(fixed_service_id or [], fixed_amount or [], strict=True))
    try:
        values = _parse_values(uow, household_id, taken_on, entered)
        if not values:
            raise InputError("Введите хотя бы одно показание")
        if action == "issue":
            bill = submit_readings_and_issue_bill(
                uow,
                household_id=household_id,
                taken_on=taken_on,
                values=values,
                fixed_amounts=_parse_amounts(fixed),
                today=today,
            )
            start = bill.period_start
            url = request.url_for(
                "bill_page", household_id=household_id, year=start.year, month=start.month
            )
            return RedirectResponse(f"{url}?issued=1", status_code=303)
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
            fixed=fixed,
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
            fixed=fixed,
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


def _parse_amounts(entered: Mapping[UUID, str]) -> dict[UUID, Decimal]:
    return {
        service_id: parse_number(amount) for service_id, amount in entered.items() if amount.strip()
    }


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
        fixed_amounts = _parse_amounts(
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


def _readings_page(
    request: Request,
    uow: UnitOfWork,
    household_id: UUID,
    taken_on: date,
    today: date,
    *,
    notice: str = "",
    entered: Mapping[UUID, str] | None = None,
    fixed: Mapping[UUID, str] | None = None,
    error: str | None = None,
    code: int = 200,
) -> HTMLResponse:
    form = queries.reading_form(uow, household_id, taken_on)
    unbilled = {month.period for month in form.unbilled}
    # Readings of that month are in already, only its bill is missing: offered with the others.
    closing = form.closing if form.closing and form.closing.period not in unbilled else None
    this_month = taken_on.replace(day=1)
    taken = [
        item.last_reading.taken_on
        for item in form.meters
        if item.last_reading and item.last_reading.taken_on >= this_month
    ]
    already_taken = bool(form.meters) and len(taken) == len(form.meters)
    return templates.TemplateResponse(
        request,
        "readings.html",
        {
            "title": "Показания",
            "household": form.household,
            "section": "readings",
            "taken_on": taken_on,
            "taken_on_title": day_month(taken_on),
            "today": today,
            "closing_title": month_name(DateRange.month_before(taken_on).start.month),
            "already_taken": day_month(max(taken)) if already_taken else "",
            "next_month": day_month((this_month + timedelta(days=32)).replace(day=1)),
            "meters": [
                {
                    "id": item.meter.id,
                    "label": item.meter.label,
                    "serial": item.meter.serial_number,
                    "kind": _kind(item.service),
                    "service": item.service.name,
                    "last": item.last_reading,
                    "last_value": number(item.last_reading.value) if item.last_reading else "",
                    "last_raw": item.last_reading.value if item.last_reading else "",
                    "last_taken_on": day_month(item.last_reading.taken_on)
                    if item.last_reading
                    else "",
                    "unit": unit_label(item.service.unit),
                    "price": money(item.price) if item.price is not None else "",
                    "price_raw": item.price if item.price is not None else "",
                    "entered": (entered or {}).get(item.meter.id, ""),
                    "correctable": item.last_reading_correctable,
                }
                for item in form.meters
            ],
            "closing": _unbilled(closing, fixed) if closing else None,
            "unbilled": [_unbilled(month, None) for month in form.unbilled],
            "last_billed": form.last_billed_period,
            "last_billed_title": _month_title(
                form.last_billed_period.start if form.last_billed_period else None
            ),
            "notice": notice,
            "error": error,
        },
        status_code=code,
    )


def _unbilled(month: queries.UnbilledMonth, fixed: Mapping[UUID, str] | None) -> dict[str, object]:
    return {
        "period": month.period,
        "title": _month_title(month.period.start),
        "name": month_name(month.period.start.month),
        "charges": [
            {
                "service_id": charge.service.id,
                "name": charge.service.name,
                "kind": _kind(charge.service),
                "tariff": "" if charge.amount is None else money(charge.amount),
                "amount": (fixed or {}).get(charge.service.id)
                or ("" if charge.amount is None else number(charge.amount)),
            }
            for charge in month.fixed_charges
        ],
    }


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
    return RedirectResponse(f"{url}?corrected=1", status_code=303)


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
            "section": "readings",
            "meter": correction.meter,
            "reading": reading,
            "taken_on": long_date(reading.taken_on),
            "value": entered if entered is not None else number(reading.value),
            "previous": previous,
            "previous_value": number(previous.value) if previous else "",
            "previous_taken_on": long_date(previous.taken_on) if previous else "",
            "error": error,
        },
        status_code=code,
    )


@router.get("/view/tariffs", response_class=HTMLResponse)
def tariffs_page(
    request: Request,
    uow: UowDep,
    today: TodayDep,
    changed: UUID | None = None,
    undone: UUID | None = None,
    error: str | None = None,
) -> HTMLResponse:
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    households = queries.list_households(uow)
    services = [_service_tariffs(item, today) for item in queries.tariff_overview(uow)]
    notice = None
    for item in services:
        if item["id"] == changed and item["change"]:
            notice = {"service_id": changed, "text": item["change"], "undo": True}
        elif item["id"] == undone:
            notice = {
                "service_id": undone,
                "text": f"{item['name']}: новая цена отменена, действует {item['price']}",
                "undo": False,
            }
    return templates.TemplateResponse(
        request,
        "tariffs.html",
        {
            "title": "Тарифы",
            # Pages of a single household link to it from the menu, this one too.
            "household": households[0] if len(households) == 1 else None,
            "section": "tariffs",
            "services": services,
            "next_month": f"{next_month:%Y-%m}",
            "notice": notice,
            "error": error,
        },
    )


def _service_tariffs(item: queries.ServiceTariffs, today: date) -> dict[str, object]:
    service, periods = item.service, item.periods
    month = DateRange.month_of(today)
    current = next((p for p in periods if p.covers(month)), None)
    upcoming = periods[0] if periods and periods[0].valid_from > month.end else None
    shown = current or (periods[0] if periods else None)
    before = periods[periods.index(shown) + 1] if shown and shown is not periods[-1] else None
    latest, replaced = (periods[0], periods[1]) if len(periods) > 1 else (None, None)
    return {
        "id": service.id,
        "name": service.name,
        "kind": _kind(service),
        "per": f"за {unit_label(service.unit)}" if service.unit else "в месяц",
        "price": money(shown.price) if shown else "",
        "since": long_date(shown.valid_from) if shown else "",
        "was": money(before.price) if before else "",
        "upcoming": {"price": money(upcoming.price), "since": long_date(upcoming.valid_from)}
        if upcoming
        else None,
        "change": f"{service.name}: {money(replaced.price)} → {money(latest.price)}"
        f" с {long_date(latest.valid_from)}"
        if latest and replaced
        else "",
        "history": [
            {"range": _range(period), "price": money(period.price)}
            for period in periods
            if period is not shown and period is not upcoming
        ],
    }


def _range(period: TariffPeriod) -> str:
    start = _month_title(period.valid_from)
    if period.valid_to is None:
        return f"с {start}"
    end = _month_title(period.valid_to)
    return start if start == end else f"{start} — {end}"


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
    return RedirectResponse(f"{url}?changed={service_id}", status_code=303)


@router.post("/view/tariffs/{service_id}/undo", response_class=HTMLResponse)
def undo_price_form(request: Request, service_id: UUID, uow: UowDep) -> Response:
    url = request.url_for("tariffs_page")
    try:
        undo_price_change(uow, service_id=service_id)
    except (DomainError, ApplicationError) as error:
        message = translate(describe_error(error)[1])
        return RedirectResponse(f"{url}?{urlencode({'error': message})}", status_code=303)
    return RedirectResponse(f"{url}?undone={service_id}", status_code=303)


def _parse_month(text: str) -> date:
    try:
        return date.fromisoformat(f"{text}-01")
    except ValueError:
        raise InputError(f"не месяц «{text}»") from None
