"""add salutations and certificate_participants tables

Revision ID: fa0c1d2e3f4a
Revises: f9b0c1d2e3f4
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fa0c1d2e3f4a"
down_revision: Union[str, None] = "f9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("salutations"):
        op.create_table(
            "salutations",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("label", sa.String(100), nullable=False),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("qualifies_for_cpd", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("label", name="uq_salutations_label"),
            sa.UniqueConstraint("code", name="uq_salutations_code"),
        )
        op.create_index("idx_salutations_active", "salutations", ["is_active"])
        op.create_index("idx_salutations_display_order", "salutations", ["display_order"])

    if not inspector.has_table("certificate_participants"):
        op.create_table(
            "certificate_participants",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("training_context_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("qualifies_for_cpd_override", sa.Boolean(), nullable=True),
            sa.Column("confirmation_status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("certificate_id", sa.BigInteger(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["training_context_id"],
                ["certificate_training_contexts.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_certificate_participants_context",
            "certificate_participants",
            ["training_context_id"],
        )
        op.create_index(
            "idx_certificate_participants_user",
            "certificate_participants",
            ["user_id"],
        )
        op.create_index(
            "idx_certificate_participants_status",
            "certificate_participants",
            ["confirmation_status"],
        )
        op.create_index(
            "idx_certificate_participants_deleted",
            "certificate_participants",
            ["deleted_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("certificate_participants"):
        op.drop_index("idx_certificate_participants_deleted", table_name="certificate_participants")
        op.drop_index("idx_certificate_participants_status", table_name="certificate_participants")
        op.drop_index("idx_certificate_participants_user", table_name="certificate_participants")
        op.drop_index("idx_certificate_participants_context", table_name="certificate_participants")
        op.drop_table("certificate_participants")

    if inspector.has_table("salutations"):
        op.drop_index("idx_salutations_display_order", table_name="salutations")
        op.drop_index("idx_salutations_active", table_name="salutations")
        op.drop_table("salutations")
