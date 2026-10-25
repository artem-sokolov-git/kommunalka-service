"""bills

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25 13:28:51.824634

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name=op.f("fk_bills_household_id_households")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bills")),
        sa.UniqueConstraint(
            "household_id", "period_start", name=op.f("uq_bills_household_id_period_start")
        ),
    )


def downgrade() -> None:
    op.drop_table("bills")
