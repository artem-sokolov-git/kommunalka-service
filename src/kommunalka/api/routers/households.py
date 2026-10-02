from uuid import UUID

from fastapi import APIRouter, status

from kommunalka.api.dependencies import UowDep
from kommunalka.api.schemas import BillIn, BillOut, HouseholdIn, HouseholdOut, MeterIn, MeterOut
from kommunalka.application import queries
from kommunalka.application.use_cases import install_meter, issue_bill, register_household

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_household(body: HouseholdIn, uow: UowDep) -> HouseholdOut:
    household = register_household(uow, name=body.name, address=body.address)
    return HouseholdOut.model_validate(household)


@router.get("")
def list_households(uow: UowDep) -> list[HouseholdOut]:
    return [HouseholdOut.model_validate(h) for h in queries.list_households(uow)]


@router.get("/{household_id}")
def get_household(household_id: UUID, uow: UowDep) -> HouseholdOut:
    return HouseholdOut.model_validate(queries.get_household(uow, household_id))


@router.post("/{household_id}/meters", status_code=status.HTTP_201_CREATED)
def create_meter(household_id: UUID, body: MeterIn, uow: UowDep) -> MeterOut:
    meter = install_meter(
        uow,
        household_id=household_id,
        service_id=body.service_id,
        serial_number=body.serial_number,
        label=body.label,
        installed_on=body.installed_on,
    )
    return MeterOut.model_validate(meter)


@router.get("/{household_id}/meters")
def list_meters(household_id: UUID, uow: UowDep) -> list[MeterOut]:
    return [MeterOut.model_validate(m) for m in queries.list_meters(uow, household_id)]


@router.post("/{household_id}/bills", status_code=status.HTTP_201_CREATED)
def create_bill(household_id: UUID, body: BillIn, uow: UowDep) -> BillOut:
    bill = issue_bill(
        uow,
        household_id=household_id,
        year=body.year,
        month=body.month,
        fixed_amounts=body.fixed_amounts,
    )
    return BillOut.from_bill(bill)


@router.get("/{household_id}/bills")
def list_bills(household_id: UUID, uow: UowDep) -> list[BillOut]:
    return [BillOut.from_bill(b) for b in queries.list_bills(uow, household_id)]
