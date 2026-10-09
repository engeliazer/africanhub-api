"""add training partner fields to invitations

Existing invitations are backfilled with DSM CPA Review Center so their
letters keep the partner logo and name they had before this change.

Revision ID: fx6d7e8f9a0b
Revises: fw5c6d7e8f9a
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fx6d7e8f9a0b"
down_revision: Union[str, None] = "fw5c6d7e8f9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("has_training_partner", sa.Boolean(), False, sa.false()),
    ("partner_name", sa.String(255), True, None),
    ("partner_logo_path", sa.String(500), True, None),
    ("partner_logo_filename", sa.String(255), True, None),
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    added_flag = "has_training_partner" not in cols
    for name, type_, nullable, default in _COLUMNS:
        if name not in cols:
            op.add_column(
                "invitations",
                sa.Column(name, type_, nullable=nullable, server_default=default),
            )
    if added_flag:
        op.execute(
            "UPDATE invitations SET has_training_partner = 1, "
            "partner_name = 'DSM CPA Review Center', "
            "partner_logo_path = 'storage/images/logoDcrc.jpg', "
            "partner_logo_filename = 'logoDcrc.jpg'"
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("invitations"):
        return
    cols = {c["name"] for c in inspector.get_columns("invitations")}
    for name, *_ in reversed(_COLUMNS):
        if name in cols:
            op.drop_column("invitations", name)
