"""add sms_count to sms_logs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SMS_CHARS_PER_SEGMENT = 160


def upgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("sms_logs"):
        return
    # Add nullable first, backfill, then enforce NOT NULL
    op.add_column("sms_logs", sa.Column("sms_count", sa.Integer(), nullable=True))
    # Backfill: ceil(message_length / 160), min 1
    conn.execute(
        text("""
            UPDATE sms_logs
            SET sms_count = GREATEST(1, CEIL(COALESCE(message_length, 0) / :segment))
            WHERE sms_count IS NULL
        """),
        {"segment": SMS_CHARS_PER_SEGMENT},
    )
    op.alter_column(
        "sms_logs",
        "sms_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("1"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("sms_logs"):
        return
    op.drop_column("sms_logs", "sms_count")
