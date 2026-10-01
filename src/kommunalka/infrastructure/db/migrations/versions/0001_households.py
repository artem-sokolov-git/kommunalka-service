"""households

Revision ID: 0001
Revises:
Create Date: 2026-10-01 19:56:35.456268

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_households")),
        sa.UniqueConstraint("address", name=op.f("uq_households_address")),
    )


def downgrade() -> None:
    op.drop_table("households")
