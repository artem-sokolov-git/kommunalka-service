"""Tariffs: the overview of prices, changing a price and undoing the change."""

from datetime import date, timedelta
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from kommunalka.application import queries
from kommunalka.application.exceptions import ApplicationError
from kommunalka.application.use_cases import change_price, undo_price_change
from kommunalka.domain import DateRange, DomainError, TariffPeriod
from kommunalka.presentation.dependencies import TodayDep, UowDep
from kommunalka.presentation.errors import describe_error
from kommunalka.presentation.web.formatting import (
    InputError,
    long_date,
    money,
    month_title,
    parse_number,
    service_kind,
    unit_label,
)
from kommunalka.presentation.web.messages import translate
from kommunalka.presentation.web.templating import templates

router = APIRouter(include_in_schema=False)


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
        "kind": service_kind(service),
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
    start = month_title(period.valid_from)
    if period.valid_to is None:
        return f"с {start}"
    end = month_title(period.valid_to)
    return start if start == end else f"{start} — {end}"


def _parse_month(text: str) -> date:
    try:
        return date.fromisoformat(f"{text}-01")
    except ValueError:
        raise InputError(f"не месяц «{text}»") from None
