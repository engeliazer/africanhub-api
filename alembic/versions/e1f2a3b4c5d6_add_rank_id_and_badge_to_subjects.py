"""add display_rank and badge flags to subjects

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-10 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column(
            "display_rank",
            sa.Integer(),
            nullable=True,
            comment="Lower = shown first",
        ),
    )
    op.add_column(
        "subjects",
        sa.Column("is_most_popular", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subjects",
        sa.Column("is_best_price", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subjects",
        sa.Column("is_most_recent", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("subjects", "is_most_recent")
    op.drop_column("subjects", "is_best_price")
    op.drop_column("subjects", "is_most_popular")
    op.drop_column("subjects", "display_rank")
