"""Link extension applications back to the original application.

Revision ID: gm3b4c5d6e7f
Revises: gl2a3b4c5d6e
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "gm3b4c5d6e7f"
down_revision = "gl2a3b4c5d6e"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("applications"):
        return
    if not _has_column(inspector, "applications", "original_application_id"):
        op.add_column(
            "applications",
            sa.Column("original_application_id", sa.BigInteger(), nullable=True),
        )
        op.create_index(
            "ix_applications_original_application_id",
            "applications",
            ["original_application_id"],
        )
        op.create_foreign_key(
            "fk_applications_original_application_id",
            "applications",
            "applications",
            ["original_application_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("applications"):
        return
    if not _has_column(inspector, "applications", "original_application_id"):
        return
    op.drop_constraint("fk_applications_original_application_id", "applications", type_="foreignkey")
    op.drop_index("ix_applications_original_application_id", table_name="applications")
    op.drop_column("applications", "original_application_id")
