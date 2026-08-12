"""add event_participants table for training calendar roster

Revision ID: fc0d1e2f3a4b
Revises: fb0c1d2e3f4b
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fc0d1e2f3a4b"
down_revision: Union[str, None] = "fb0c1d2e3f4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("event_participants"):
        return

    op.create_table(
        "event_participants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("salutation_id", sa.BigInteger(), nullable=True),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_event_participants_event", "event_participants", ["event_id"])
    op.create_index("idx_event_participants_user", "event_participants", ["user_id"])
    op.create_index("idx_event_participants_salutation", "event_participants", ["salutation_id"])
    op.create_index("idx_event_participants_deleted", "event_participants", ["deleted_at"])


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_participants"):
        return

    op.drop_index("idx_event_participants_deleted", table_name="event_participants")
    op.drop_index("idx_event_participants_salutation", table_name="event_participants")
    op.drop_index("idx_event_participants_user", table_name="event_participants")
    op.drop_index("idx_event_participants_event", table_name="event_participants")
    op.drop_table("event_participants")
