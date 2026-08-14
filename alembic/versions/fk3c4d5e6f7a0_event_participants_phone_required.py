"""require phone on event_participants and unique per event

Revision ID: fk3c4d5e6f7a0
Revises: fj2b3c4d5e6f
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "fk3c4d5e6f7a0"
down_revision: Union[str, None] = "fj2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_participants"):
        return

    columns = {col["name"] for col in inspect(conn).get_columns("event_participants")}
    if "phone" in columns:
        op.alter_column(
            "event_participants",
            "phone",
            existing_type=sa.String(50),
            nullable=False,
        )

    existing_indexes = {idx["name"] for idx in inspect(conn).get_indexes("event_participants")}
    if "idx_event_participants_phone" not in existing_indexes:
        op.create_index("idx_event_participants_phone", "event_participants", ["phone"])
    if "uq_event_participants_event_phone" not in existing_indexes:
        op.create_index(
            "uq_event_participants_event_phone",
            "event_participants",
            ["event_id", "phone"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_participants"):
        return

    existing_indexes = {idx["name"] for idx in inspect(conn).get_indexes("event_participants")}
    for name in ("uq_event_participants_event_phone", "idx_event_participants_phone"):
        if name in existing_indexes:
            op.drop_index(name, table_name="event_participants")

    op.alter_column(
        "event_participants",
        "phone",
        existing_type=sa.String(50),
        nullable=True,
    )
