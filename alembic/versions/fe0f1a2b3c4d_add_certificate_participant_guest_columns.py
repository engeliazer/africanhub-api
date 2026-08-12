"""add guest columns to certificate_participants for event walk-ins

Revision ID: fe0f1a2b3c4d
Revises: fd0e1f2a3b4c
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fe0f1a2b3c4d"
down_revision: Union[str, None] = "fd0e1f2a3b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
    if "full_name" not in columns:
        op.alter_column(
            "certificate_participants",
            "user_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )
        op.add_column(
            "certificate_participants",
            sa.Column("full_name", sa.String(255), nullable=True),
        )
        op.add_column(
            "certificate_participants",
            sa.Column("salutation_id", sa.BigInteger(), nullable=True),
        )
        op.add_column(
            "certificate_participants",
            sa.Column("event_participant_id", sa.BigInteger(), nullable=True),
        )
        op.create_index(
            "idx_certificate_participants_salutation",
            "certificate_participants",
            ["salutation_id"],
        )
        op.create_index(
            "idx_certificate_participants_event_participant",
            "certificate_participants",
            ["event_participant_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
    if "full_name" in columns:
        op.drop_index(
            "idx_certificate_participants_event_participant",
            table_name="certificate_participants",
        )
        op.drop_index(
            "idx_certificate_participants_salutation",
            table_name="certificate_participants",
        )
        op.drop_column("certificate_participants", "event_participant_id")
        op.drop_column("certificate_participants", "salutation_id")
        op.drop_column("certificate_participants", "full_name")
        op.alter_column(
            "certificate_participants",
            "user_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
