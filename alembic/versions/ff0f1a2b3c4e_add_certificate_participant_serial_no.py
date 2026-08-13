"""add serial_no to certificate_participants

Revision ID: ff0f1a2b3c4e
Revises: fe0f1a2b3c4d
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "ff0f1a2b3c4e"
down_revision: Union[str, None] = "fe0f1a2b3c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
    if "serial_no" not in columns:
        op.add_column(
            "certificate_participants",
            sa.Column("serial_no", sa.String(255), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("certificate_participants")}
    if "uq_certificate_participants_serial_no" not in indexes:
        op.create_index(
            "uq_certificate_participants_serial_no",
            "certificate_participants",
            ["serial_no"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("certificate_participants")}
    if "uq_certificate_participants_serial_no" in indexes:
        op.drop_index(
            "uq_certificate_participants_serial_no",
            table_name="certificate_participants",
        )

    columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
    if "serial_no" in columns:
        op.drop_column("certificate_participants", "serial_no")
