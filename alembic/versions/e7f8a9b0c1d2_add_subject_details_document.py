"""add details_document_url to subjects

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column(
            "details_document_url",
            sa.String(length=512),
            nullable=True,
            comment="Public URL to subject details document (PDF/DOC/etc.)",
        ),
    )


def downgrade() -> None:
    op.drop_column("subjects", "details_document_url")
