"""add invitation_trainers table

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("invitation_trainers"):
        return

    op.create_table(
        "invitation_trainers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("designation", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("qualifications", sa.Text(), nullable=True),
        sa.Column("photo", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitation_trainers_id", "invitation_trainers", ["id"])
    op.create_index("ix_invitation_trainers_full_name", "invitation_trainers", ["full_name"])


def downgrade() -> None:
    op.drop_index("ix_invitation_trainers_full_name", table_name="invitation_trainers")
    op.drop_index("ix_invitation_trainers_id", table_name="invitation_trainers")
    op.drop_table("invitation_trainers")
