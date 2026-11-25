"""Study periods and the subject extension price.

Revision ID: gk1f2a3b4c5d
Revises: gj0e1f2a3b4c
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "gk1f2a3b4c5d"
down_revision = "gj0e1f2a3b4c"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("subjects") and not _has_column(inspector, "subjects", "extension_price"):
        op.add_column("subjects", sa.Column("extension_price", sa.BigInteger(), nullable=True))

    inspector = inspect(conn)
    if not inspector.has_table("study_periods"):
        op.create_table(
            "study_periods",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("application_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("subject_id", sa.BigInteger(), nullable=False),
            sa.Column("period_type", sa.String(length=20), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("allocated_days", sa.Integer(), nullable=False),
            sa.Column("expected_end_date", sa.Date(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_study_periods_id", "study_periods", ["id"])
        op.create_index("ix_study_periods_application_id", "study_periods", ["application_id"])
        op.create_index("ix_study_periods_user_id", "study_periods", ["user_id"])
        op.create_index("ix_study_periods_subject_id", "study_periods", ["subject_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table("study_periods"):
        op.drop_table("study_periods")
    inspector = inspect(conn)
    if inspector.has_table("subjects") and _has_column(inspector, "subjects", "extension_price"):
        op.drop_column("subjects", "extension_price")
