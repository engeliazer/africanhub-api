"""event letter request verification flags as boolean

Revision ID: fj2b3c4d5e6f
Revises: fi1a2b3c4d5e6
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "fj2b3c4d5e6f"
down_revision: Union[str, None] = "fi1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, column: str) -> bool:
    return column in {col["name"] for col in inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_letter_requests"):
        return

    if _has_column(conn, "event_letter_requests", "phone_verification_code"):
        op.alter_column(
            "event_letter_requests",
            "phone_verification_code",
            existing_type=sa.String(10),
            type_=sa.String(6),
            existing_nullable=True,
        )
    if _has_column(conn, "event_letter_requests", "email_verification_code"):
        op.alter_column(
            "event_letter_requests",
            "email_verification_code",
            existing_type=sa.String(10),
            type_=sa.String(6),
            existing_nullable=True,
        )

    if not _has_column(conn, "event_letter_requests", "phone_verified"):
        op.add_column(
            "event_letter_requests",
            sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    if not _has_column(conn, "event_letter_requests", "email_verified"):
        op.add_column(
            "event_letter_requests",
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    if _has_column(conn, "event_letter_requests", "phone_verification_status"):
        op.drop_column("event_letter_requests", "phone_verification_status")
    if _has_column(conn, "event_letter_requests", "email_verification_status"):
        op.drop_column("event_letter_requests", "email_verification_status")


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_letter_requests"):
        return

    if not _has_column(conn, "event_letter_requests", "phone_verification_status"):
        op.add_column(
            "event_letter_requests",
            sa.Column("phone_verification_status", sa.String(20), nullable=False, server_default="pending"),
        )
    if not _has_column(conn, "event_letter_requests", "email_verification_status"):
        op.add_column(
            "event_letter_requests",
            sa.Column("email_verification_status", sa.String(20), nullable=False, server_default="pending"),
        )

    if _has_column(conn, "event_letter_requests", "phone_verified"):
        op.drop_column("event_letter_requests", "phone_verified")
    if _has_column(conn, "event_letter_requests", "email_verified"):
        op.drop_column("event_letter_requests", "email_verified")
