"""Store the chosen salutation on public training registrations.

Revision ID: gp6e7f8a9b0c
Revises: go5d6e7f8a9b
Create Date: 2026-11-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "gp6e7f8a9b0c"
down_revision = "go5d6e7f8a9b"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column) -> bool:
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("event_training_registrations"):
        return
    if _has_column(inspector, "event_training_registrations", "salutation_id"):
        return
    op.add_column(
        "event_training_registrations",
        sa.Column("salutation_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_event_training_registrations_salutation_id",
        "event_training_registrations",
        ["salutation_id"],
    )
    if inspector.has_table("salutations"):
        op.create_foreign_key(
            "fk_event_training_registrations_salutation_id",
            "event_training_registrations",
            "salutations",
            ["salutation_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("event_training_registrations"):
        return
    if not _has_column(inspector, "event_training_registrations", "salutation_id"):
        return
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("event_training_registrations")}
    if "fk_event_training_registrations_salutation_id" in fk_names:
        op.drop_constraint(
            "fk_event_training_registrations_salutation_id",
            "event_training_registrations",
            type_="foreignkey",
        )
    indexes = {item["name"] for item in inspector.get_indexes("event_training_registrations")}
    if "ix_event_training_registrations_salutation_id" in indexes:
        op.drop_index(
            "ix_event_training_registrations_salutation_id",
            table_name="event_training_registrations",
        )
    op.drop_column("event_training_registrations", "salutation_id")
