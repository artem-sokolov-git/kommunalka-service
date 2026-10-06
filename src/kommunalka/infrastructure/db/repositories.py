from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Row, delete, insert, select, update
from sqlalchemy.orm import InstrumentedAttribute

from kommunalka.domain import (
    Bill,
    BillLine,
    FixedBillLine,
    Household,
    Meter,
    MeteredBillLine,
    Reading,
    Service,
    TariffPeriod,
    Unit,
)
from kommunalka.infrastructure.db.models import (
    Base,
    BillLineRow,
    BillRow,
    HouseholdRow,
    MeterRow,
    ReadingRow,
    ServiceRow,
    TariffPeriodRow,
)


class SqlHouseholdRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def get(self, household_id: UUID, /) -> Household | None:
        row = self._connection.execute(
            select(HouseholdRow).where(HouseholdRow.id == household_id)
        ).one_or_none()
        return None if row is None else _to_household(row)

    def list_all(self) -> list[Household]:
        rows = self._connection.execute(select(HouseholdRow).order_by(HouseholdRow.name))
        return [_to_household(row) for row in rows]

    def save(self, household: Household, /) -> None:
        _upsert(
            self._connection,
            HouseholdRow,
            HouseholdRow.id,
            {"id": household.id, "name": household.name, "address": household.address},
        )


class SqlServiceRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def get(self, service_id: UUID, /) -> Service | None:
        row = self._connection.execute(
            select(ServiceRow).where(ServiceRow.id == service_id)
        ).one_or_none()
        return None if row is None else _to_service(row)

    def list_all(self) -> list[Service]:
        rows = self._connection.execute(select(ServiceRow).order_by(ServiceRow.name))
        return [_to_service(row) for row in rows]

    def save(self, service: Service, /) -> None:
        _upsert(
            self._connection,
            ServiceRow,
            ServiceRow.id,
            {"id": service.id, "name": service.name, "unit": service.unit},
        )


class SqlMeterRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def get(self, meter_id: UUID, /) -> Meter | None:
        row = self._connection.execute(
            select(MeterRow).where(MeterRow.id == meter_id)
        ).one_or_none()
        return None if row is None else _to_meter(row)

    def list_all(self) -> list[Meter]:
        rows = self._connection.execute(select(MeterRow).order_by(MeterRow.installed_on))
        return [_to_meter(row) for row in rows]

    def list_by_household(self, household_id: UUID, /) -> list[Meter]:
        rows = self._connection.execute(
            select(MeterRow)
            .where(MeterRow.household_id == household_id)
            .order_by(MeterRow.installed_on)
        )
        return [_to_meter(row) for row in rows]

    def save(self, meter: Meter, /) -> None:
        _upsert(
            self._connection,
            MeterRow,
            MeterRow.id,
            {
                "id": meter.id,
                "household_id": meter.household_id,
                "service_id": meter.service_id,
                "serial_number": meter.serial_number,
                "label": meter.label,
                "installed_on": meter.installed_on,
                "model": meter.model,
                "removed_on": meter.removed_on,
            },
        )


class SqlReadingRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def get(self, reading_id: UUID, /) -> Reading | None:
        row = self._connection.execute(
            select(ReadingRow).where(ReadingRow.id == reading_id)
        ).one_or_none()
        return None if row is None else _to_reading(row)

    def list_by_meter(self, meter_id: UUID, /) -> list[Reading]:
        rows = self._connection.execute(
            select(ReadingRow).where(ReadingRow.meter_id == meter_id).order_by(ReadingRow.taken_on)
        )
        return [_to_reading(row) for row in rows]

    def save(self, reading: Reading, /) -> None:
        _upsert(
            self._connection,
            ReadingRow,
            ReadingRow.id,
            {
                "id": reading.id,
                "meter_id": reading.meter_id,
                "value": reading.value,
                "taken_on": reading.taken_on,
                "previous_taken_on": reading.previous_taken_on,
                "billing_month": reading.billing_period.start,
            },
        )


class SqlTariffPeriodRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def list_all(self) -> list[TariffPeriod]:
        rows = self._connection.execute(
            select(TariffPeriodRow).order_by(TariffPeriodRow.valid_from)
        )
        return [_to_tariff_period(row) for row in rows]

    def list_by_service(self, service_id: UUID, /) -> list[TariffPeriod]:
        rows = self._connection.execute(
            select(TariffPeriodRow)
            .where(TariffPeriodRow.service_id == service_id)
            .order_by(TariffPeriodRow.valid_from)
        )
        return [_to_tariff_period(row) for row in rows]

    def save(self, tariff_period: TariffPeriod, /) -> None:
        _upsert(
            self._connection,
            TariffPeriodRow,
            TariffPeriodRow.id,
            {
                "id": tariff_period.id,
                "service_id": tariff_period.service_id,
                "price": tariff_period.price,
                "valid_from": tariff_period.valid_from,
                "valid_to": tariff_period.valid_to,
            },
        )

    def delete(self, tariff_period_id: UUID, /) -> None:
        self._connection.execute(
            delete(TariffPeriodRow).where(TariffPeriodRow.id == tariff_period_id)
        )


class SqlBillRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def list_by_household(self, household_id: UUID, /) -> list[Bill]:
        bill_rows = self._connection.execute(
            select(BillRow)
            .where(BillRow.household_id == household_id)
            .order_by(BillRow.period_start)
        ).all()
        line_rows = self._connection.execute(
            select(BillLineRow)
            .where(BillLineRow.bill_id.in_([row.id for row in bill_rows]))
            .order_by(BillLineRow.position)
        )
        lines: defaultdict[UUID, list[BillLine]] = defaultdict(list)
        for line_row in line_rows:
            lines[line_row.bill_id].append(_to_bill_line(line_row))
        return [
            Bill(
                id=row.id,
                household_id=row.household_id,
                period_start=row.period_start,
                period_end=row.period_end,
                lines=tuple(lines[row.id]),
            )
            for row in bill_rows
        ]

    def save(self, bill: Bill, /) -> None:
        _upsert(
            self._connection,
            BillRow,
            BillRow.id,
            {
                "id": bill.id,
                "household_id": bill.household_id,
                "period_start": bill.period_start,
                "period_end": bill.period_end,
            },
        )
        self._connection.execute(delete(BillLineRow).where(BillLineRow.bill_id == bill.id))
        if bill.lines:
            self._connection.execute(
                insert(BillLineRow),
                [
                    _bill_line_values(bill.id, position, line)
                    for position, line in enumerate(bill.lines)
                ],
            )


def _upsert(
    connection: Connection,
    model: type[Base],
    id_column: InstrumentedAttribute[UUID],
    values: dict[str, Any],
) -> None:
    result = connection.execute(update(model).where(id_column == values["id"]).values(values))
    if result.rowcount == 0:
        connection.execute(insert(model).values(values))


def _to_household(row: Row[Any]) -> Household:
    return Household(id=row.id, name=row.name, address=row.address)


def _to_service(row: Row[Any]) -> Service:
    return Service(id=row.id, name=row.name, unit=None if row.unit is None else Unit(row.unit))


def _to_meter(row: Row[Any]) -> Meter:
    return Meter(
        id=row.id,
        household_id=row.household_id,
        service_id=row.service_id,
        serial_number=row.serial_number,
        label=row.label,
        installed_on=row.installed_on,
        model=row.model,
        removed_on=row.removed_on,
    )


def _to_reading(row: Row[Any]) -> Reading:
    return Reading(
        id=row.id,
        meter_id=row.meter_id,
        value=row.value,
        taken_on=row.taken_on,
        previous_taken_on=row.previous_taken_on,
    )


def _to_tariff_period(row: Row[Any]) -> TariffPeriod:
    return TariffPeriod(
        id=row.id,
        service_id=row.service_id,
        price=row.price,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
    )


def _to_bill_line(row: Row[Any]) -> BillLine:
    if row.amount is not None:
        return FixedBillLine(service_id=row.service_id, amount=row.amount)
    return MeteredBillLine(service_id=row.service_id, quantity=row.quantity, price=row.price)


def _bill_line_values(bill_id: UUID, position: int, line: BillLine) -> dict[str, Any]:
    values: dict[str, Any] = {
        "bill_id": bill_id,
        "service_id": line.service_id,
        "position": position,
        "quantity": None,
        "price": None,
        "amount": None,
    }
    match line:
        case MeteredBillLine():
            values |= {"quantity": line.quantity, "price": line.price}
        case FixedBillLine():
            values |= {"amount": line.amount}
    return values
