"""Remove the role/position column from testimonials.

Revision ID: go5d6e7f8a9b
Revises: gn4c5d6e7f8a
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "go5d6e7f8a9b"
down_revision = "gn4c5d6e7f8a"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table("testimonials") and _has_column(inspector, "testimonials", "role"):
        op.drop_column("testimonials", "role")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table("testimonials") and not _has_column(inspector, "testimonials", "role"):
        op.add_column("testimonials", sa.Column("role", sa.String(length=255), nullable=True))
