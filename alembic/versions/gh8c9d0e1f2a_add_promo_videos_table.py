"""Add promo_videos for public VdoCipher playback.

Revision ID: gh8c9d0e1f2a
Revises: gg7b8c9d0e1f
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "gh8c9d0e1f2a"
down_revision = "gg7b8c9d0e1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("promo_videos"):
        return

    op.create_table(
        "promo_videos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("video_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("vdocipher_video_id", sa.String(255), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("video_duration", sa.Float(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_promo_videos_slug"),
    )
    op.create_index("ix_promo_videos_id", "promo_videos", ["id"])
    op.create_index("ix_promo_videos_slug", "promo_videos", ["slug"])
    op.create_index("ix_promo_videos_status", "promo_videos", ["status"])
    op.create_index("ix_promo_videos_video_status", "promo_videos", ["video_status"])
    op.create_index("ix_promo_videos_vdocipher_video_id", "promo_videos", ["vdocipher_video_id"])


def downgrade() -> None:
    op.drop_index("ix_promo_videos_vdocipher_video_id", table_name="promo_videos")
    op.drop_index("ix_promo_videos_video_status", table_name="promo_videos")
    op.drop_index("ix_promo_videos_status", table_name="promo_videos")
    op.drop_index("ix_promo_videos_slug", table_name="promo_videos")
    op.drop_index("ix_promo_videos_id", table_name="promo_videos")
    op.drop_table("promo_videos")
