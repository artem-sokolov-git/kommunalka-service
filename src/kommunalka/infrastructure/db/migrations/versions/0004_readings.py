"""readings

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25 13:28:51.824634

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "readings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meter_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("taken_on", sa.Date(), nullable=False),
        sa.Column("previous_taken_on", sa.Date(), nullable=True),
        sa.Column("billing_month", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meter_id"], ["meters.id"], name=op.f("fk_readings_meter_id_meters")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_readings")),
        sa.UniqueConstraint(
            "meter_id", "billing_month", name=op.f("uq_readings_meter_id_billing_month")
        ),
    )


def downgrade() -> None:
    op.drop_table("readings")
