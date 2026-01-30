"""add testimonials table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("testimonials"):
        return
    op.create_table(
        "testimonials",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("photo", sa.String(500), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testimonials_id", "testimonials", ["id"])
    op.create_index("idx_testimonials_user", "testimonials", ["user_id"])
    op.create_index("idx_testimonials_approved", "testimonials", ["is_approved"])
    op.create_index("idx_testimonials_active", "testimonials", ["is_active"])
    op.create_index("idx_testimonials_deleted", "testimonials", ["deleted_at"])


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("testimonials"):
        return
    op.drop_index("idx_testimonials_deleted", table_name="testimonials")
    op.drop_index("idx_testimonials_active", table_name="testimonials")
    op.drop_index("idx_testimonials_approved", table_name="testimonials")
    op.drop_index("idx_testimonials_user", table_name="testimonials")
    op.drop_index("ix_testimonials_id", table_name="testimonials")
    op.drop_table("testimonials")
