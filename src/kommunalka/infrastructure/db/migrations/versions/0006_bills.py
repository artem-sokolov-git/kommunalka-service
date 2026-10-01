"""bills

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01 19:56:36.298532

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
    op.create_table(
        "bill_lines",
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.String(), nullable=True),
        sa.Column("price", sa.String(), nullable=True),
        sa.Column("amount", sa.String(), nullable=True),
        sa.CheckConstraint(
            "(quantity IS NOT NULL AND price IS NOT NULL AND amount IS NULL) OR (quantity IS NULL AND price IS NULL AND amount IS NOT NULL)",
            name=op.f("ck_bill_lines_metered_or_fixed"),
        ),
        sa.ForeignKeyConstraint(
            ["bill_id"], ["bills.id"], name=op.f("fk_bill_lines_bill_id_bills"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_bill_lines_service_id_services")
        ),
        sa.PrimaryKeyConstraint("bill_id", "service_id", name=op.f("pk_bill_lines")),
    )


def downgrade() -> None:
    op.drop_table("bill_lines")
    op.drop_table("bills")
