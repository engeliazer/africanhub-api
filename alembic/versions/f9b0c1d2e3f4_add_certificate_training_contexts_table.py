"""add certificate_training_contexts table

Revision ID: f9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "f9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("certificate_training_contexts"):
        return

    op.create_table(
        "certificate_training_contexts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("training_type", sa.String(20), nullable=False),
        sa.Column("training_id", sa.BigInteger(), nullable=False),
        sa.Column("certificate_template_id", sa.BigInteger(), nullable=False),
        sa.Column("host_mode", sa.String(20), nullable=False, server_default="single"),
        sa.Column("host_organization_name", sa.String(255), nullable=False),
        sa.Column("invited_organization_name", sa.String(255), nullable=True),
        sa.Column("home_logo_url", sa.String(500), nullable=True),
        sa.Column("invited_logo_url", sa.String(500), nullable=True),
        sa.Column("subject_title", sa.String(500), nullable=False),
        sa.Column("venue_text", sa.String(500), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("cpd_hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cert_number_pattern", sa.String(255), nullable=False),
        sa.Column("home_code", sa.String(50), nullable=False),
        sa.Column("invited_code", sa.String(50), nullable=True),
        sa.Column("signatory_override", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["certificate_template_id"], ["certificate_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certificate_training_contexts_id", "certificate_training_contexts", ["id"])
    op.create_index(
        "idx_certificate_training_contexts_training",
        "certificate_training_contexts",
        ["training_type", "training_id"],
    )
    op.create_index(
        "idx_certificate_training_contexts_template",
        "certificate_training_contexts",
        ["certificate_template_id"],
    )
    op.create_index(
        "idx_certificate_training_contexts_deleted",
        "certificate_training_contexts",
        ["deleted_at"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("certificate_training_contexts"):
        return
    op.drop_index("idx_certificate_training_contexts_deleted", table_name="certificate_training_contexts")
    op.drop_index("idx_certificate_training_contexts_template", table_name="certificate_training_contexts")
    op.drop_index("idx_certificate_training_contexts_training", table_name="certificate_training_contexts")
    op.drop_index("ix_certificate_training_contexts_id", table_name="certificate_training_contexts")
    op.drop_table("certificate_training_contexts")
