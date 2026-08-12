"""add certificate_templates and certificate_template_signatories tables

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("certificate_templates"):
        op.create_table(
            "certificate_templates",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("background_url", sa.String(500), nullable=False),
            sa.Column("background_filename", sa.String(255), nullable=True),
            sa.Column(
                "certificate_title",
                sa.String(255),
                nullable=False,
                server_default="Certificate of Participation",
            ),
            sa.Column(
                "participation_prefix",
                sa.String(500),
                nullable=False,
                server_default="Participated in the training on",
            ),
            sa.Column(
                "venue_template",
                sa.String(500),
                nullable=False,
                server_default="held at {venue}",
            ),
            sa.Column(
                "date_template",
                sa.String(500),
                nullable=False,
                server_default="from {start_date} to {end_date}",
            ),
            sa.Column(
                "cpd_template",
                sa.String(1000),
                nullable=False,
                server_default=(
                    "from {start_date} to {end_date} and qualified for the award of "
                    "{cpd_hours} hours of Continuing Professional Development"
                ),
            ),
            sa.Column("field_layout", sa.JSON(), nullable=True),
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
        op.create_index("ix_certificate_templates_id", "certificate_templates", ["id"])
        op.create_index("idx_certificate_templates_active", "certificate_templates", ["is_active"])
        op.create_index("idx_certificate_templates_deleted", "certificate_templates", ["deleted_at"])

    if not inspector.has_table("certificate_template_signatories"):
        op.create_table(
            "certificate_template_signatories",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("template_id", sa.BigInteger(), nullable=False),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("signature_url", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["template_id"], ["certificate_templates.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_certificate_template_signatories_id",
            "certificate_template_signatories",
            ["id"],
        )
        op.create_index(
            "idx_certificate_template_signatories_template",
            "certificate_template_signatories",
            ["template_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("certificate_template_signatories"):
        op.drop_index(
            "idx_certificate_template_signatories_template",
            table_name="certificate_template_signatories",
        )
        op.drop_index(
            "ix_certificate_template_signatories_id",
            table_name="certificate_template_signatories",
        )
        op.drop_table("certificate_template_signatories")

    if inspector.has_table("certificate_templates"):
        op.drop_index("idx_certificate_templates_deleted", table_name="certificate_templates")
        op.drop_index("idx_certificate_templates_active", table_name="certificate_templates")
        op.drop_index("ix_certificate_templates_id", table_name="certificate_templates")
        op.drop_table("certificate_templates")
