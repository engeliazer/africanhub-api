"""add error_message to mail_batch_recipients

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("mail_batch_recipients"):
        return
    columns = {c["name"] for c in inspect(conn).get_columns("mail_batch_recipients")}
    if "error_message" not in columns:
        op.add_column("mail_batch_recipients", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("mail_batch_recipients"):
        return
    columns = {c["name"] for c in inspect(conn).get_columns("mail_batch_recipients")}
    if "error_message" in columns:
        op.drop_column("mail_batch_recipients", "error_message")
