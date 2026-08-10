"""add rank_id and badge to subjects

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

subject_badge_enum = sa.Enum(
    "most_popular",
    "best_price",
    "most_recent",
    name="subject_badge",
)


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column(
            "rank_id",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Display priority; lower values appear first",
        ),
    )
    subject_badge_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "subjects",
        sa.Column("badge", subject_badge_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subjects", "badge")
    op.drop_column("subjects", "rank_id")
    subject_badge_enum.drop(op.get_bind(), checkfirst=True)
