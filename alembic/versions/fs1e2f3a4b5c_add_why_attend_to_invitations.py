"""add why_attend_intro and why_attend_points to invitations

Revision ID: fs1e2f3a4b5c
Revises: fr0d1e2f3a4b
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fs1e2f3a4b5c"
down_revision: Union[str, None] = "fr0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("why_attend_intro", "why_attend_points")


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
