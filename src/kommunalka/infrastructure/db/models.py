"""Table definitions. Used through SQLAlchemy Core only, never through an ORM session."""

from datetime import date
from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import CheckConstraint, Dialect, ForeignKey, MetaData, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class DecimalString(TypeDecorator[Decimal]):
    """Exact decimal stored as text, since SQLite has no decimal type."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        return None if value is None else str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
        }
    )
    type_annotation_map: ClassVar[dict[Any, Any]] = {Decimal: DecimalString()}


class HouseholdRow(Base):
    __tablename__ = "households"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    address: Mapped[str] = mapped_column(unique=True)


class ServiceRow(Base):
    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    unit: Mapped[str | None]


class MeterRow(Base):
    __tablename__ = "meters"
    __table_args__ = (UniqueConstraint("household_id", "label"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"))
    serial_number: Mapped[str] = mapped_column(unique=True)
    label: Mapped[str]
    installed_on: Mapped[date]
    removed_on: Mapped[date | None]


class ReadingRow(Base):
    __tablename__ = "readings"
    __table_args__ = (UniqueConstraint("meter_id", "billing_month"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    meter_id: Mapped[UUID] = mapped_column(ForeignKey("meters.id"))
    value: Mapped[Decimal]
    taken_on: Mapped[date]
    previous_taken_on: Mapped[date | None]
    # Denormalized start of Reading.billing_period to enforce one reading per month.
    billing_month: Mapped[date]


class TariffPeriodRow(Base):
    __tablename__ = "tariff_periods"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"))
    price: Mapped[Decimal]
    valid_from: Mapped[date]
    valid_to: Mapped[date]


class BillRow(Base):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("household_id", "period_start"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    period_start: Mapped[date]
    period_end: Mapped[date]


class BillLineRow(Base):
    """Metered lines store quantity and price, fixed lines store a ready amount."""

    __tablename__ = "bill_lines"
    __table_args__ = (
        CheckConstraint(
            "(quantity IS NOT NULL AND price IS NOT NULL AND amount IS NULL)"
            " OR (quantity IS NULL AND price IS NULL AND amount IS NOT NULL)",
            name="metered_or_fixed",
        ),
    )

    bill_id: Mapped[UUID] = mapped_column(
        ForeignKey("bills.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"), primary_key=True)
    # Order of the line in Bill.lines.
    position: Mapped[int]
    quantity: Mapped[Decimal | None]
    price: Mapped[Decimal | None]
    amount: Mapped[Decimal | None]
