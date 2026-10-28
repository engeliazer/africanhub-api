"""add public website notifications and visitor read tracking

Revision ID: gb2c3d4e5f6a
Revises: ga1b2c3d4e5f
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "gb2c3d4e5f6a"
down_revision: Union[str, None] = "ga1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "public_notifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False, server_default="general"),
        sa.Column("link", sa.String(length=1000), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_notifications_id", "public_notifications", ["id"])

    op.create_table(
        "public_notification_reads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("visitor_id", sa.String(length=255), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["notification_id"], ["public_notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "visitor_id", name="uq_public_notification_read_visitor"),
    )
    op.create_index("ix_public_notification_reads_id", "public_notification_reads", ["id"])
    op.create_index("ix_public_notification_reads_notification_id", "public_notification_reads", ["notification_id"])
    op.create_index("ix_public_notification_reads_visitor_id", "public_notification_reads", ["visitor_id"])


def downgrade() -> None:
    op.drop_index("ix_public_notification_reads_visitor_id", table_name="public_notification_reads")
    op.drop_index("ix_public_notification_reads_notification_id", table_name="public_notification_reads")
    op.drop_index("ix_public_notification_reads_id", table_name="public_notification_reads")
    op.drop_table("public_notification_reads")
    op.drop_index("ix_public_notifications_id", table_name="public_notifications")
    op.drop_table("public_notifications")
