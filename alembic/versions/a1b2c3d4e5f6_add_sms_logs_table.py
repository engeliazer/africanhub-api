"""add sms_logs table

Revision ID: a1b2c3d4e5f6
Revises: 6e04b5d9a8c2
Create Date: 2025-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "6e04b5d9a8c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sms_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sender_id", sa.String(100), nullable=False),
        sa.Column("recipient", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("message_length", sa.Integer(), nullable=False),
        sa.Column("process_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="mshastra"),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("api_response_raw", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_logs_id", "sms_logs", ["id"])
    op.create_index("ix_sms_logs_recipient", "sms_logs", ["recipient"])
    op.create_index("ix_sms_logs_process_name", "sms_logs", ["process_name"])
    op.create_index("ix_sms_logs_created_at", "sms_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sms_logs_created_at", table_name="sms_logs")
    op.drop_index("ix_sms_logs_process_name", table_name="sms_logs")
    op.drop_index("ix_sms_logs_recipient", table_name="sms_logs")
    op.drop_index("ix_sms_logs_id", table_name="sms_logs")
    op.drop_table("sms_logs")
