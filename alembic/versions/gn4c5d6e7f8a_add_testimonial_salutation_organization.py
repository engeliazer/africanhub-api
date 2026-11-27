"""Add salutation and organization to testimonials.

Revision ID: gn4c5d6e7f8a
Revises: gm3b4c5d6e7f
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "gn4c5d6e7f8a"
down_revision = "gm3b4c5d6e7f"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("testimonials"):
        return
    if not _has_column(inspector, "testimonials", "salutation_id"):
        op.add_column("testimonials", sa.Column("salutation_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_testimonials_salutation_id", "testimonials", ["salutation_id"])
        if inspector.has_table("salutations"):
            op.create_foreign_key(
                "fk_testimonials_salutation_id",
                "testimonials",
                "salutations",
                ["salutation_id"],
                ["id"],
                ondelete="SET NULL",
            )
    inspector = inspect(conn)
    if not _has_column(inspector, "testimonials", "organization"):
        op.add_column("testimonials", sa.Column("organization", sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("testimonials"):
        return
    if _has_column(inspector, "testimonials", "organization"):
        op.drop_column("testimonials", "organization")
    if _has_column(inspector, "testimonials", "salutation_id"):
        if inspector.has_table("salutations"):
            op.drop_constraint("fk_testimonials_salutation_id", "testimonials", type_="foreignkey")
        op.drop_index("ix_testimonials_salutation_id", table_name="testimonials")
        op.drop_column("testimonials", "salutation_id")
