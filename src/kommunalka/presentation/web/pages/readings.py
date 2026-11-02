"""Meter readings: entering them (optionally issuing the bill they close) and correcting one."""

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.application.exceptions import ApplicationError
from kommunalka.application.unit_of_work import UnitOfWork
from kommunalka.application.use_cases import (
    correct_reading,
    submit_readings,
    submit_readings_and_issue_bill,
)
from kommunalka.domain import DateRange, DomainError
from kommunalka.presentation.dependencies import TodayDep, UowDep
from kommunalka.presentation.errors import describe_error
from kommunalka.presentation.web.formatting import (
    InputError,
    day_month,
    long_date,
    money,
    month_name,
    month_title,
    number,
    parse_amounts,
    parse_number,
    service_kind,
    unit_label,
)
from kommunalka.presentation.web.messages import translate
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)


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
                fixed_amounts=parse_amounts(fixed),
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
                    "kind": service_kind(item.service),
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
            "last_billed_title": month_title(
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
        "title": month_title(month.period.start),
        "name": month_name(month.period.start.month),
        "charges": [
            {
                "service_id": charge.service.id,
                "name": charge.service.name,
                "kind": service_kind(charge.service),
                "tariff": "" if charge.amount is None else money(charge.amount),
                "amount": (fixed or {}).get(charge.service.id)
                or ("" if charge.amount is None else number(charge.amount)),
            }
            for charge in month.fixed_charges
        ],
    }


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
