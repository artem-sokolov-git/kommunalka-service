from uuid import UUID

from fastapi import APIRouter, status

from kommunalka.api.dependencies import UowDep
from kommunalka.api.schemas import MeterOut, MeterRemovalIn, ReadingIn, ReadingOut
from kommunalka.application import queries
from kommunalka.application.use_cases import remove_meter, submit_reading

router = APIRouter(prefix="/meters", tags=["meters"])


@router.post("/{meter_id}/removal")
def create_meter_removal(meter_id: UUID, body: MeterRemovalIn, uow: UowDep) -> MeterOut:
    return MeterOut.model_validate(remove_meter(uow, meter_id=meter_id, removed_on=body.removed_on))


@router.post("/{meter_id}/readings", status_code=status.HTTP_201_CREATED)
def create_reading(meter_id: UUID, body: ReadingIn, uow: UowDep) -> ReadingOut:
    reading = submit_reading(uow, meter_id=meter_id, value=body.value, taken_on=body.taken_on)
    return ReadingOut.model_validate(reading)


@router.get("/{meter_id}/readings")
def list_readings(meter_id: UUID, uow: UowDep) -> list[ReadingOut]:
    return [ReadingOut.model_validate(r) for r in queries.list_readings(uow, meter_id)]
