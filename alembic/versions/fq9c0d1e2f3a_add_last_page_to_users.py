"""add last_page to users

Revision ID: fq9c0d1e2f3a
Revises: fp8b9c0d1e2f
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fq9c0d1e2f3a"
down_revision: Union[str, None] = "fp8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("users"):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "last_page" not in cols:
        op.add_column("users", sa.Column("last_page", sa.String(length=500), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("users"):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "last_page" in cols:
        op.drop_column("users", "last_page")
