"""add partner_organizations table

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-10 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("partner_organizations"):
        return
    op.create_table(
        "partner_organizations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("logo", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_partner_organizations_id", "partner_organizations", ["id"])
    op.create_index("idx_partner_organizations_active", "partner_organizations", ["is_active"])
    op.create_index("idx_partner_organizations_deleted", "partner_organizations", ["deleted_at"])


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("partner_organizations"):
        return
    op.drop_index("idx_partner_organizations_deleted", table_name="partner_organizations")
    op.drop_index("idx_partner_organizations_active", table_name="partner_organizations")
    op.drop_index("ix_partner_organizations_id", table_name="partner_organizations")
    op.drop_table("partner_organizations")
