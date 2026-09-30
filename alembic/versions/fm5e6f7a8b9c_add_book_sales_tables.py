"""add book sales pricing listings and orders

Revision ID: fm5e6f7a8b9c
Revises: fl4d5e6f7a8b
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fm5e6f7a8b9c"
down_revision: Union[str, None] = "fl4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("edition_prices"):
        op.create_table(
            "edition_prices",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("edition_reference_id", sa.String(100), nullable=False),
            sa.Column("new_buyer_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("previous_buyer_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("effective_from", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("effective_to", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_edition_prices_id", "edition_prices", ["id"])
        op.create_index("idx_edition_prices_edition", "edition_prices", ["edition_reference_id"])
        op.create_index("idx_edition_prices_active", "edition_prices", ["is_active"])

    if not inspector.has_table("book_listings"):
        op.create_table(
            "book_listings",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("edition_reference_id", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="UNLISTED"),
            sa.Column("listed_at", sa.DateTime(), nullable=True),
            sa.Column("listed_by", sa.BigInteger(), nullable=True),
            sa.Column("unlisted_at", sa.DateTime(), nullable=True),
            sa.Column("unlisted_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["listed_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["unlisted_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("edition_reference_id", name="uq_book_listings_edition"),
        )
        op.create_index("ix_book_listings_id", "book_listings", ["id"])
        op.create_index("idx_book_listings_status", "book_listings", ["status"])

    if not inspector.has_table("book_orders"):
        op.create_table(
            "book_orders",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("order_number", sa.String(50), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_number", name="uq_book_orders_order_number"),
        )
        op.create_index("ix_book_orders_id", "book_orders", ["id"])
        op.create_index("idx_book_orders_user", "book_orders", ["user_id"])
        op.create_index("idx_book_orders_status", "book_orders", ["status"])

    if not inspector.has_table("book_order_items"):
        op.create_table(
            "book_order_items",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("book_reference_id", sa.String(100), nullable=False),
            sa.Column("edition_reference_id", sa.String(100), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["book_orders.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id", "edition_reference_id", name="uq_book_order_item_edition"),
        )
        op.create_index("ix_book_order_items_id", "book_order_items", ["id"])
        op.create_index("idx_book_order_items_book", "book_order_items", ["book_reference_id"])
        op.create_index("idx_book_order_items_edition", "book_order_items", ["edition_reference_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("book_order_items"):
        op.drop_index("idx_book_order_items_edition", table_name="book_order_items")
        op.drop_index("idx_book_order_items_book", table_name="book_order_items")
        op.drop_index("ix_book_order_items_id", table_name="book_order_items")
        op.drop_table("book_order_items")

    if inspector.has_table("book_orders"):
        op.drop_index("idx_book_orders_status", table_name="book_orders")
        op.drop_index("idx_book_orders_user", table_name="book_orders")
        op.drop_index("ix_book_orders_id", table_name="book_orders")
        op.drop_table("book_orders")

    if inspector.has_table("book_listings"):
        op.drop_index("idx_book_listings_status", table_name="book_listings")
        op.drop_index("ix_book_listings_id", table_name="book_listings")
        op.drop_table("book_listings")

    if inspector.has_table("edition_prices"):
        op.drop_index("idx_edition_prices_active", table_name="edition_prices")
        op.drop_index("idx_edition_prices_edition", table_name="edition_prices")
        op.drop_index("ix_edition_prices_id", table_name="edition_prices")
        op.drop_table("edition_prices")
