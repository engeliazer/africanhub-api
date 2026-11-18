"""Add event_resources table for downloadable zip packs.

Revision ID: ge5f6a7b8c9d
Revises: gd4e5f6a7b8c
Create Date: 2026-11-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "ge5f6a7b8c9d"
down_revision = "gd4e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("event_resources"):
        return

    op.create_table(
        "event_resources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("extension_type", sa.String(20), nullable=False, server_default="zip"),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_event_resources_id", "event_resources", ["id"])
    op.create_index("ix_event_resources_event_id", "event_resources", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_resources_event_id", table_name="event_resources")
    op.drop_index("ix_event_resources_id", table_name="event_resources")
    op.drop_table("event_resources")
