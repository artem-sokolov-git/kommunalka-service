from uuid import UUID

from fastapi import APIRouter

from kommunalka.api.dependencies import UowDep
from kommunalka.api.schemas import ReadingCorrectionIn, ReadingOut
from kommunalka.application.use_cases import correct_reading

router = APIRouter(prefix="/readings", tags=["readings"])


@router.patch("/{reading_id}")
def update_reading(reading_id: UUID, body: ReadingCorrectionIn, uow: UowDep) -> ReadingOut:
    return ReadingOut.model_validate(correct_reading(uow, reading_id=reading_id, value=body.value))
