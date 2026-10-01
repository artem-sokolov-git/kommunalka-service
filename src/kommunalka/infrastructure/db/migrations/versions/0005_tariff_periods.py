"""tariff_periods

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01 19:56:36.134382

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tariff_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.String(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_tariff_periods_service_id_services")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tariff_periods")),
    )


def downgrade() -> None:
    op.drop_table("tariff_periods")
