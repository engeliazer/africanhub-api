"""default certificate_participants confirmation_status to confirmed

Revision ID: fh0f1a2b3c50
Revises: fg0f1a2b3c4f
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fh0f1a2b3c50"
down_revision: Union[str, None] = "fg0f1a2b3c4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    op.alter_column(
        "certificate_participants",
        "confirmation_status",
        existing_type=sa.String(20),
        server_default="confirmed",
        nullable=False,
    )
    op.execute(
        """
        UPDATE certificate_participants
        SET confirmation_status = 'confirmed'
        WHERE confirmation_status = 'pending'
          AND deleted_at IS NULL
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    op.alter_column(
        "certificate_participants",
        "confirmation_status",
        existing_type=sa.String(20),
        server_default="pending",
        nullable=False,
    )
