"""add last_seen_at to users

Revision ID: fp8b9c0d1e2f
Revises: fo7a8b9c0d1e
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fp8b9c0d1e2f"
down_revision: Union[str, None] = "fo7a8b9c0d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("users"):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "last_seen_at" not in cols:
        op.add_column("users", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    if "ix_users_last_seen_at" not in indexes:
        op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("users"):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    if "ix_users_last_seen_at" in indexes:
        op.drop_index("ix_users_last_seen_at", table_name="users")
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "last_seen_at" in cols:
        op.drop_column("users", "last_seen_at")
