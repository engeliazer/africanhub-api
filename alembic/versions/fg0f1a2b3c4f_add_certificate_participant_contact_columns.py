"""add email and organization to certificate_participants

Revision ID: fg0f1a2b3c4f
Revises: ff0f1a2b3c4e
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fg0f1a2b3c4f"
down_revision: Union[str, None] = "ff0f1a2b3c4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
    if "email" not in columns:
        op.add_column("certificate_participants", sa.Column("email", sa.String(255), nullable=True))
    if "organization" not in columns:
        op.add_column("certificate_participants", sa.Column("organization", sa.String(255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("certificate_participants"):
        return

    columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
    if "organization" in columns:
        op.drop_column("certificate_participants", "organization")
    if "email" in columns:
        op.drop_column("certificate_participants", "email")
