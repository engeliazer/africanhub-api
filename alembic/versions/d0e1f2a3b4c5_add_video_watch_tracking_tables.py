"""add video watch tracking tables

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("video_watch_sessions"):
        op.create_table(
            "video_watch_sessions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("session_token", sa.String(36), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("material_id", sa.BigInteger(), nullable=False),
            sa.Column("watched_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_position_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_heartbeat_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["material_id"], ["subtopic_materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_token"),
        )
        op.create_index("ix_video_watch_sessions_id", "video_watch_sessions", ["id"])
        op.create_index("ix_video_watch_sessions_session_token", "video_watch_sessions", ["session_token"])
        op.create_index("ix_video_watch_sessions_user_id", "video_watch_sessions", ["user_id"])
        op.create_index("ix_video_watch_sessions_material_id", "video_watch_sessions", ["material_id"])

    if not inspector.has_table("video_watch_progress"):
        op.create_table(
            "video_watch_progress",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("material_id", sa.BigInteger(), nullable=False),
            sa.Column("total_watched_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_position_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("session_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_percentage", sa.Float(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
            sa.Column("first_watched_at", sa.DateTime(), nullable=True),
            sa.Column("last_watched_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["material_id"], ["subtopic_materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "material_id", name="uq_video_watch_progress_user_material"),
        )
        op.create_index("ix_video_watch_progress_id", "video_watch_progress", ["id"])
        op.create_index("ix_video_watch_progress_user_id", "video_watch_progress", ["user_id"])
        op.create_index("ix_video_watch_progress_material_id", "video_watch_progress", ["material_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("video_watch_progress"):
        op.drop_index("ix_video_watch_progress_material_id", table_name="video_watch_progress")
        op.drop_index("ix_video_watch_progress_user_id", table_name="video_watch_progress")
        op.drop_index("ix_video_watch_progress_id", table_name="video_watch_progress")
        op.drop_table("video_watch_progress")

    if inspector.has_table("video_watch_sessions"):
        op.drop_index("ix_video_watch_sessions_material_id", table_name="video_watch_sessions")
        op.drop_index("ix_video_watch_sessions_user_id", table_name="video_watch_sessions")
        op.drop_index("ix_video_watch_sessions_session_token", table_name="video_watch_sessions")
        op.drop_index("ix_video_watch_sessions_id", table_name="video_watch_sessions")
        op.drop_table("video_watch_sessions")
