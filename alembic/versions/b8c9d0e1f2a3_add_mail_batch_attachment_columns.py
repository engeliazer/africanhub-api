"""add mail batch attachment columns

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("mail_batches"):
        return
    columns = {c["name"] for c in inspect(conn).get_columns("mail_batches")}
    if "attachment_path" not in columns:
        op.add_column("mail_batches", sa.Column("attachment_path", sa.String(500), nullable=True))
    if "attachment_filename" not in columns:
        op.add_column("mail_batches", sa.Column("attachment_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("mail_batches"):
        return
    columns = {c["name"] for c in inspect(conn).get_columns("mail_batches")}
    if "attachment_filename" in columns:
        op.drop_column("mail_batches", "attachment_filename")
    if "attachment_path" in columns:
        op.drop_column("mail_batches", "attachment_path")
