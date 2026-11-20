"""Add optional cover image URL to promo videos.

Revision ID: gi9d0e1f2a3b
Revises: gh8c9d0e1f2a
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "gi9d0e1f2a3b"
down_revision = "gh8c9d0e1f2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("promo_videos"):
        return
    columns = {column["name"] for column in inspector.get_columns("promo_videos")}
    if "cover_url" in columns:
        return
    op.add_column("promo_videos", sa.Column("cover_url", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("promo_videos"):
        return
    columns = {column["name"] for column in inspector.get_columns("promo_videos")}
    if "cover_url" not in columns:
        return
    op.drop_column("promo_videos", "cover_url")
