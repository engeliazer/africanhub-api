"""add active_session_id to users

Revision ID: fo7a8b9c0d1e
Revises: fn6f7a8b9c0d
Create Date: 2026-10-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fo7a8b9c0d1e"
down_revision: Union[str, None] = "fn6f7a8b9c0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("users"):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "active_session_id" not in cols:
        op.add_column("users", sa.Column("active_session_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("users"):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "active_session_id" in cols:
        op.drop_column("users", "active_session_id")
