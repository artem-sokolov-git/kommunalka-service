from uuid import UUID

from fastapi import APIRouter, status

from kommunalka.api.dependencies import UowDep
from kommunalka.api.schemas import ServiceIn, ServiceOut, TariffPeriodIn, TariffPeriodOut
from kommunalka.application import queries
from kommunalka.application.use_cases import add_service, set_tariff

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


@router.get("/{service_id}/tariffs")
def list_tariff_periods(service_id: UUID, uow: UowDep) -> list[TariffPeriodOut]:
    return [TariffPeriodOut.model_validate(t) for t in queries.list_tariff_periods(uow, service_id)]
