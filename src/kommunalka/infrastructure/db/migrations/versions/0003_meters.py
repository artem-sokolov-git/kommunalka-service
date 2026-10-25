"""meters

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-25 13:28:51.824634

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("serial_number", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("installed_on", sa.Date(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("removed_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name=op.f("fk_meters_household_id_households")
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_meters_service_id_services")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meters")),
        sa.UniqueConstraint("household_id", "label", name=op.f("uq_meters_household_id_label")),
        sa.UniqueConstraint("serial_number", name=op.f("uq_meters_serial_number")),
    )


def downgrade() -> None:
    op.drop_table("meters")
