"""meter_model_open_tariffs

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-05 09:57:32.767004

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("meters", schema=None) as batch_op:
        batch_op.add_column(sa.Column("model", sa.String(), nullable=True))

    with op.batch_alter_table("tariff_periods", schema=None) as batch_op:
        batch_op.alter_column("valid_to", existing_type=sa.DATE(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("tariff_periods", schema=None) as batch_op:
        batch_op.alter_column("valid_to", existing_type=sa.DATE(), nullable=False)

    with op.batch_alter_table("meters", schema=None) as batch_op:
        batch_op.drop_column("model")
