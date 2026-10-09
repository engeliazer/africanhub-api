"""add payment_intro to invitations

Revision ID: fv4b5c6d7e8f
Revises: fu3a4b5c6d7e
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fv4b5c6d7e8f"
down_revision: Union[str, None] = "fu3a4b5c6d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    if "payment_intro" not in cols:
        op.add_column("invitations", sa.Column("payment_intro", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    if "payment_intro" in cols:
        op.drop_column("invitations", "payment_intro")
