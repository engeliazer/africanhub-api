"""add certificates table for issued certificate output

Revision ID: fd0e1f2a3b4c
Revises: fc0d1e2f3a4b
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fd0e1f2a3b4c"
down_revision: Union[str, None] = "fc0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("certificates"):
        return

    op.create_table(
        "certificates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("training_context_id", sa.BigInteger(), nullable=False),
        sa.Column("participant_id", sa.BigInteger(), nullable=False),
        sa.Column("training_id", sa.BigInteger(), nullable=False),
        sa.Column("cert_number", sa.String(255), nullable=False),
        sa.Column("qualifies_for_cpd", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("pdf_url", sa.String(500), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
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
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["certificate_participants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cert_number", name="uq_certificates_cert_number"),
    )
    op.create_index("idx_certificates_context", "certificates", ["training_context_id"])
    op.create_index("idx_certificates_participant", "certificates", ["participant_id"])
    op.create_index("idx_certificates_training", "certificates", ["training_id"])
    op.create_index("idx_certificates_deleted", "certificates", ["deleted_at"])


def downgrade() -> None:
    conn = op.get_bind()
    if not inspect(conn).has_table("certificates"):
        return

    op.drop_index("idx_certificates_deleted", table_name="certificates")
    op.drop_index("idx_certificates_training", table_name="certificates")
    op.drop_index("idx_certificates_participant", table_name="certificates")
    op.drop_index("idx_certificates_context", table_name="certificates")
    op.drop_table("certificates")
