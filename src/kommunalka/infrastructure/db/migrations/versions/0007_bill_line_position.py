"""bill_line_position

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01 20:04:08.358056

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing lines get position 0: their original order wasn't stored.
    with op.batch_alter_table("bill_lines", schema=None) as batch_op:
        batch_op.add_column(sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("bill_lines", schema=None) as batch_op:
        batch_op.alter_column("position", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("bill_lines", schema=None) as batch_op:
        batch_op.drop_column("position")
