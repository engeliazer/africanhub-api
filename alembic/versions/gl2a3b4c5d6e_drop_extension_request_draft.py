"""Drop the unused extension-request tables if an earlier draft created them.

Revision ID: gl2a3b4c5d6e
Revises: gk1f2a3b4c5d
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "gl2a3b4c5d6e"
down_revision = "gk1f2a3b4c5d"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("study_periods"):
        for fk in inspector.get_foreign_keys("study_periods"):
            if "extension_request_id" in (fk.get("constrained_columns") or []) and fk.get("name"):
                op.drop_constraint(fk["name"], "study_periods", type_="foreignkey")
        for index in inspector.get_indexes("study_periods"):
            if index.get("column_names") == ["extension_request_id"] and index.get("name"):
                op.drop_index(index["name"], table_name="study_periods")
        inspector = inspect(conn)
        if _has_column(inspector, "study_periods", "extension_request_id"):
            op.drop_column("study_periods", "extension_request_id")

    inspector = inspect(conn)
    if inspector.has_table("study_extension_requests"):
        op.drop_table("study_extension_requests")

    inspector = inspect(conn)
    if inspector.has_table("subjects"):
        if not _has_column(inspector, "subjects", "extension_price"):
            op.add_column("subjects", sa.Column("extension_price", sa.BigInteger(), nullable=True))
        if _has_column(inspector, "subjects", "extension_duration_days"):
            op.drop_column("subjects", "extension_duration_days")
        if _has_column(inspector, "subjects", "extension_fee"):
            op.drop_column("subjects", "extension_fee")


def downgrade() -> None:
    return None
