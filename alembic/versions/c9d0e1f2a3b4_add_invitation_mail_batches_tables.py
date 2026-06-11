"""add invitation_mail_batches tables

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("invitation_mail_batches"):
        return

    op.create_table(
        "invitation_mail_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("interval_limit", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", name="mailbatchstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("invitation_template_path", sa.String(500), nullable=True),
        sa.Column("invitation_template_filename", sa.String(255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitation_mail_batches_id", "invitation_mail_batches", ["id"])

    op.create_table(
        "invitation_mail_batch_recipients",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("organization", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSED", "FAILED", name="mailrecipientstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["invitation_mail_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitation_mail_batch_recipients_id", "invitation_mail_batch_recipients", ["id"])
    op.create_index(
        "ix_invitation_mail_batch_recipients_batch_id",
        "invitation_mail_batch_recipients",
        ["batch_id"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("invitation_mail_batches"):
        return
    op.drop_index("ix_invitation_mail_batch_recipients_batch_id", table_name="invitation_mail_batch_recipients")
    op.drop_index("ix_invitation_mail_batch_recipients_id", table_name="invitation_mail_batch_recipients")
    op.drop_table("invitation_mail_batch_recipients")
    op.drop_index("ix_invitation_mail_batches_id", table_name="invitation_mail_batches")
    op.drop_table("invitation_mail_batches")
