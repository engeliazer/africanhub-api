"""add additional PDF attachment to invitations

Revision ID: fy7e8f9a0b1c
Revises: fx6d7e8f9a0b
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fy7e8f9a0b1c"
down_revision: Union[str, None] = "fx6d7e8f9a0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("additional_attachment_path", sa.String(500)),
    ("additional_attachment_filename", sa.String(255)),
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    for name, type_ in _COLUMNS:
        if name not in cols:
            op.add_column("invitations", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    for name, _ in reversed(_COLUMNS):
        if name in cols:
            op.drop_column("invitations", name)
