"""add book purchase entitlements and order payment fields

Revision ID: fn6f7a8b9c0d
Revises: fm5e6f7a8b9c
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fn6f7a8b9c0d"
down_revision: Union[str, None] = "fm5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("book_orders"):
        cols = {c["name"] for c in inspector.get_columns("book_orders")}
        if "payment_id" not in cols:
            op.add_column("book_orders", sa.Column("payment_id", sa.BigInteger(), nullable=True))
            op.add_column("book_orders", sa.Column("attachment_path", sa.String(500), nullable=True))
            op.add_column("book_orders", sa.Column("attachment_filename", sa.String(255), nullable=True))
            op.create_foreign_key("fk_book_orders_payment", "book_orders", "payments", ["payment_id"], ["id"])
            op.create_index("idx_book_orders_payment", "book_orders", ["payment_id"])

    if not inspector.has_table("user_paid_book_editions"):
        op.create_table(
            "user_paid_book_editions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("book_reference_id", sa.String(100), nullable=False),
            sa.Column("edition_reference_id", sa.String(100), nullable=False),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("payment_id", sa.BigInteger(), nullable=False),
            sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
            sa.Column("paid_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["order_id"], ["book_orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "edition_reference_id", name="uq_user_paid_edition"),
        )
        op.create_index("idx_user_paid_editions_user", "user_paid_book_editions", ["user_id"])
        op.create_index("idx_user_paid_editions_edition", "user_paid_book_editions", ["edition_reference_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table("user_paid_book_editions"):
        op.drop_table("user_paid_book_editions")
