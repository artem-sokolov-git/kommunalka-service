from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from kommunalka.domain import Bill, FixedBillLine, MeteredBillLine, Unit


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class HouseholdIn(Schema):
    name: str
    address: str


class HouseholdOut(Schema):
    id: UUID
    name: str
    address: str


class ServiceIn(Schema):
    name: str
    unit: Unit | None = None


class ServiceOut(Schema):
    id: UUID
    name: str
    unit: Unit | None
    is_metered: bool


class MeterIn(Schema):
    service_id: UUID
    serial_number: str
    label: str
    installed_on: date


class MeterRemovalIn(Schema):
    removed_on: date


class MeterOut(Schema):
    id: UUID
    household_id: UUID
    service_id: UUID
    serial_number: str
    label: str
    installed_on: date
    removed_on: date | None
    is_active: bool


class ReadingIn(Schema):
    value: Decimal
    taken_on: date


class ReadingCorrectionIn(Schema):
    value: Decimal


class ReadingOut(Schema):
    id: UUID
    meter_id: UUID
    value: Decimal
    taken_on: date
    previous_taken_on: date | None


class TariffPeriodIn(Schema):
    price: Decimal
    valid_from: date
    valid_to: date


class TariffPeriodOut(Schema):
    id: UUID
    service_id: UUID
    price: Decimal
    valid_from: date
    valid_to: date


Month = Annotated[int, Field(ge=1, le=12)]


class BillIn(Schema):
    year: int
    month: Month
    fixed_amounts: dict[UUID, Decimal] = {}


class MeteredBillLineOut(Schema):
    kind: Literal["metered"] = "metered"
    service_id: UUID
    service_name: str
    quantity: Decimal
    price: Decimal
    amount: Decimal


class FixedBillLineOut(Schema):
    kind: Literal["fixed"] = "fixed"
    service_id: UUID
    service_name: str
    amount: Decimal


class BillOut(Schema):
    id: UUID
    household_id: UUID
    period_start: date
    period_end: date
    lines: list[MeteredBillLineOut | FixedBillLineOut]
    total: Decimal

    @classmethod
    def from_bill(cls, bill: Bill, service_names: Mapping[UUID, str]) -> "BillOut":
        return cls(
            id=bill.id,
            household_id=bill.household_id,
            period_start=bill.period_start,
            period_end=bill.period_end,
            lines=[_line_out(line, service_names[line.service_id]) for line in bill.lines],
            total=bill.total,
        )


def _line_out(
    line: MeteredBillLine | FixedBillLine, service_name: str
) -> MeteredBillLineOut | FixedBillLineOut:
    match line:
        case MeteredBillLine():
            return MeteredBillLineOut(
                service_id=line.service_id,
                service_name=service_name,
                quantity=line.quantity,
                price=line.price,
                amount=line.amount,
            )
        case FixedBillLine():
            return FixedBillLineOut(
                service_id=line.service_id, service_name=service_name, amount=line.amount
            )
