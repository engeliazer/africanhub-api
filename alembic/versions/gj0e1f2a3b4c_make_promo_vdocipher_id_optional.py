"""Allow promo videos to be saved before a VdoCipher id is linked.

Revision ID: gj0e1f2a3b4c
Revises: gi9d0e1f2a3b
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "gj0e1f2a3b4c"
down_revision = "gi9d0e1f2a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("promo_videos"):
        return
    column = next(
        (item for item in inspector.get_columns("promo_videos") if item["name"] == "vdocipher_video_id"),
        None,
    )
    if column is None or column.get("nullable"):
        return
    op.alter_column(
        "promo_videos",
        "vdocipher_video_id",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "promo_videos",
        "vdocipher_video_id",
        existing_type=sa.String(length=255),
        nullable=False,
    )
