"""services

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25 13:28:51.824634

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )


def downgrade() -> None:
    op.drop_table("services")
