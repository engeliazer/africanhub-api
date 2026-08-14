"""expand event_letter_requests with names, contact, salutation, verification

Revision ID: fi1a2b3c4d5e6
Revises: fh0f1a2b3c50
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "fi1a2b3c4d5e6"
down_revision: Union[str, None] = "fh0f1a2b3c50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, column: str) -> bool:
    return column in {col["name"] for col in inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_letter_requests"):
        return

    if not _has_column(conn, "event_letter_requests", "first_name"):
        op.add_column("event_letter_requests", sa.Column("first_name", sa.String(100), nullable=True))
    if not _has_column(conn, "event_letter_requests", "middle_name"):
        op.add_column("event_letter_requests", sa.Column("middle_name", sa.String(100), nullable=True))
    if not _has_column(conn, "event_letter_requests", "last_name"):
        op.add_column("event_letter_requests", sa.Column("last_name", sa.String(100), nullable=True))
    if not _has_column(conn, "event_letter_requests", "salutation_id"):
        op.add_column("event_letter_requests", sa.Column("salutation_id", sa.BigInteger(), nullable=True))
    if not _has_column(conn, "event_letter_requests", "phone"):
        op.add_column("event_letter_requests", sa.Column("phone", sa.String(50), nullable=True))
    if not _has_column(conn, "event_letter_requests", "phone_verification_code"):
        op.add_column("event_letter_requests", sa.Column("phone_verification_code", sa.String(10), nullable=True))
    if not _has_column(conn, "event_letter_requests", "email_verification_code"):
        op.add_column("event_letter_requests", sa.Column("email_verification_code", sa.String(10), nullable=True))
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

    if _has_column(conn, "event_letter_requests", "full_name"):
        conn.execute(
            text(
                """
                UPDATE event_letter_requests
                SET first_name = COALESCE(NULLIF(first_name, ''), full_name),
                    last_name = COALESCE(NULLIF(last_name, ''), '-')
                WHERE first_name IS NULL OR first_name = ''
                """
            )
        )

    conn.execute(
        text(
            """
            UPDATE event_letter_requests elr
            SET salutation_id = (
                SELECT id FROM salutations WHERE code = 'none' LIMIT 1
            )
            WHERE elr.salutation_id IS NULL
            """
        )
    )

    conn.execute(
        text(
            """
            UPDATE event_letter_requests
            SET phone = CONCAT('legacy', id)
            WHERE phone IS NULL OR phone = ''
            """
        )
    )

    conn.execute(
        text(
            """
            UPDATE event_letter_requests
            SET email = CONCAT('legacy-', id, '@placeholder.local')
            WHERE email IS NULL OR email = ''
            """
        )
    )

    op.alter_column("event_letter_requests", "first_name", existing_type=sa.String(100), nullable=False)
    op.alter_column("event_letter_requests", "last_name", existing_type=sa.String(100), nullable=False)
    op.alter_column("event_letter_requests", "salutation_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("event_letter_requests", "phone", existing_type=sa.String(50), nullable=False)
    op.alter_column("event_letter_requests", "email", existing_type=sa.String(255), nullable=False)

    if _has_column(conn, "event_letter_requests", "full_name"):
        op.drop_column("event_letter_requests", "full_name")

    existing_indexes = {idx["name"] for idx in inspect(conn).get_indexes("event_letter_requests")}
    if "uq_event_letter_requests_event_phone" not in existing_indexes:
        op.create_index(
            "uq_event_letter_requests_event_phone",
            "event_letter_requests",
            ["event_id", "phone"],
            unique=True,
        )
    if "uq_event_letter_requests_event_email" not in existing_indexes:
        op.create_index(
            "uq_event_letter_requests_event_email",
            "event_letter_requests",
            ["event_id", "email"],
            unique=True,
        )
    if "ix_event_letter_requests_salutation_id" not in existing_indexes:
        op.create_index("ix_event_letter_requests_salutation_id", "event_letter_requests", ["salutation_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("event_letter_requests"):
        return

    existing_indexes = {idx["name"] for idx in inspect(conn).get_indexes("event_letter_requests")}
    for name in (
        "ix_event_letter_requests_salutation_id",
        "uq_event_letter_requests_event_email",
        "uq_event_letter_requests_event_phone",
    ):
        if name in existing_indexes:
            op.drop_index(name, table_name="event_letter_requests")

    if not _has_column(conn, "event_letter_requests", "full_name"):
        op.add_column("event_letter_requests", sa.Column("full_name", sa.String(255), nullable=True))

    conn.execute(
        text(
            """
            UPDATE event_letter_requests
            SET full_name = TRIM(CONCAT_WS(' ', first_name, middle_name, last_name))
            """
        )
    )

    op.alter_column("event_letter_requests", "full_name", existing_type=sa.String(255), nullable=False)

    for column in (
        "email_verification_status",
        "phone_verification_status",
        "email_verification_code",
        "phone_verification_code",
        "phone",
        "salutation_id",
        "last_name",
        "middle_name",
        "first_name",
    ):
        if _has_column(conn, "event_letter_requests", column):
            op.drop_column("event_letter_requests", column)

    op.alter_column("event_letter_requests", "email", existing_type=sa.String(255), nullable=True)
