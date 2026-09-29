"""add book subject links and access grant logs

Revision ID: fl4d5e6f7a8b
Revises: fk3c4d5e6f7a0
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fl4d5e6f7a8b"
down_revision: Union[str, None] = "fk3c4d5e6f7a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("book_subject_links"):
        op.create_table(
            "book_subject_links",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("lms_book_id", sa.Integer(), nullable=False),
            sa.Column("subject_id", sa.BigInteger(), nullable=False),
            sa.Column("title", sa.String(500), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("lms_book_id", "subject_id", name="uq_book_subject_link"),
        )
        op.create_index("ix_book_subject_links_id", "book_subject_links", ["id"])
        op.create_index("idx_book_subject_links_lms_book", "book_subject_links", ["lms_book_id"])
        op.create_index("idx_book_subject_links_subject", "book_subject_links", ["subject_id"])
        op.create_index("idx_book_subject_links_active", "book_subject_links", ["is_active"])
        op.create_index("idx_book_subject_links_deleted", "book_subject_links", ["deleted_at"])

    if not inspector.has_table("book_access_grant_logs"):
        op.create_table(
            "book_access_grant_logs",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("lms_book_id", sa.Integer(), nullable=False),
            sa.Column("lms_grant_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="active"),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_book_access_grant_logs_id", "book_access_grant_logs", ["id"])
        op.create_index("idx_book_access_grant_logs_user", "book_access_grant_logs", ["user_id"])
        op.create_index("idx_book_access_grant_logs_book", "book_access_grant_logs", ["lms_book_id"])
        op.create_index("idx_book_access_grant_logs_grant", "book_access_grant_logs", ["lms_grant_id"])
        op.create_index("idx_book_access_grant_logs_status", "book_access_grant_logs", ["status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("book_access_grant_logs"):
        op.drop_index("idx_book_access_grant_logs_status", table_name="book_access_grant_logs")
        op.drop_index("idx_book_access_grant_logs_grant", table_name="book_access_grant_logs")
        op.drop_index("idx_book_access_grant_logs_book", table_name="book_access_grant_logs")
        op.drop_index("idx_book_access_grant_logs_user", table_name="book_access_grant_logs")
        op.drop_index("ix_book_access_grant_logs_id", table_name="book_access_grant_logs")
        op.drop_table("book_access_grant_logs")

    if inspector.has_table("book_subject_links"):
        op.drop_index("idx_book_subject_links_deleted", table_name="book_subject_links")
        op.drop_index("idx_book_subject_links_active", table_name="book_subject_links")
        op.drop_index("idx_book_subject_links_subject", table_name="book_subject_links")
        op.drop_index("idx_book_subject_links_lms_book", table_name="book_subject_links")
        op.drop_index("ix_book_subject_links_id", table_name="book_subject_links")
        op.drop_table("book_subject_links")
