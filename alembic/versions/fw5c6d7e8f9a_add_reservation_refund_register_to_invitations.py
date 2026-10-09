"""add reservation_details, refund_policy and how_to_register to invitations

Revision ID: fw5c6d7e8f9a
Revises: fv4b5c6d7e8f
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fw5c6d7e8f9a"
down_revision: Union[str, None] = "fv4b5c6d7e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("reservation_details", "refund_policy", "how_to_register")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    for name in _COLUMNS:
        if name not in cols:
            op.add_column("invitations", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    for name in reversed(_COLUMNS):
        if name in cols:
            op.drop_column("invitations", name)
