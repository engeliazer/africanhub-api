"""add investment_details to invitations

Revision ID: fu3a4b5c6d7e
Revises: ft2f3a4b5c6d
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fu3a4b5c6d7e"
down_revision: Union[str, None] = "ft2f3a4b5c6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    if "investment_details" not in cols:
        op.add_column("invitations", sa.Column("investment_details", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    if "investment_details" in cols:
        op.drop_column("invitations", "investment_details")
