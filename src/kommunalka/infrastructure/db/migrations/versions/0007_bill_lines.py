"""bill_lines

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-25 13:28:51.824634

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bill_lines",
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
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
