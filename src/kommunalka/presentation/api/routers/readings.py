from uuid import UUID

from fastapi import APIRouter

from kommunalka.application.use_cases import correct_reading
from kommunalka.presentation.api.schemas import ReadingCorrectionIn, ReadingOut
from kommunalka.presentation.dependencies import UowDep

router = APIRouter(prefix="/readings", tags=["readings"])


@router.patch("/{reading_id}")
def update_reading(reading_id: UUID, body: ReadingCorrectionIn, uow: UowDep) -> ReadingOut:
    return ReadingOut.model_validate(correct_reading(uow, reading_id=reading_id, value=body.value))
