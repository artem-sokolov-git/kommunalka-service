from uuid import UUID

from fastapi import APIRouter, status

from kommunalka.application import queries
from kommunalka.application.use_cases import (
    add_service,
    change_price,
    set_tariff,
    undo_price_change,
)
from kommunalka.presentation.api.schemas import (
    PriceChangeIn,
    ServiceIn,
    ServiceOut,
    TariffPeriodIn,
    TariffPeriodOut,
)
from kommunalka.presentation.dependencies import UowDep

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceIn, uow: UowDep) -> ServiceOut:
    return ServiceOut.model_validate(add_service(uow, name=body.name, unit=body.unit))


@router.get("")
def list_services(uow: UowDep) -> list[ServiceOut]:
    return [ServiceOut.model_validate(s) for s in queries.list_services(uow)]


@router.post("/{service_id}/tariffs", status_code=status.HTTP_201_CREATED)
def create_tariff_period(service_id: UUID, body: TariffPeriodIn, uow: UowDep) -> TariffPeriodOut:
    tariff_period = set_tariff(
        uow,
        service_id=service_id,
        price=body.price,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
    )
    return TariffPeriodOut.model_validate(tariff_period)


@router.post("/{service_id}/prices", status_code=status.HTTP_201_CREATED)
def create_price_change(service_id: UUID, body: PriceChangeIn, uow: UowDep) -> TariffPeriodOut:
    """Start a new price on the first day of a month, closing the current one the day before."""
    tariff_period = change_price(
        uow, service_id=service_id, price=body.price, valid_from=body.valid_from
    )
    return TariffPeriodOut.model_validate(tariff_period)


@router.delete("/{service_id}/prices/latest")
def delete_latest_price(service_id: UUID, uow: UowDep) -> TariffPeriodOut | None:
    """Undo the latest price unless a bill uses it; return the price in force again."""
    current = undo_price_change(uow, service_id=service_id)
    return TariffPeriodOut.model_validate(current) if current else None


@router.get("/{service_id}/tariffs")
def list_tariff_periods(service_id: UUID, uow: UowDep) -> list[TariffPeriodOut]:
    return [TariffPeriodOut.model_validate(t) for t in queries.list_tariff_periods(uow, service_id)]
