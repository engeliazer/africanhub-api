"""add mobile_device_id to user_devices

Revision ID: ga1b2c3d4e5f
Revises: fz8a9b0c1d2e
Create Date: 2026-10-21

Stores the hash of vendor id and android id sent by the mobile app.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "ga1b2c3d4e5f"
down_revision: Union[str, None] = "fz8a9b0c1d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("user_devices"):
        return
    cols = {c["name"] for c in inspector.get_columns("user_devices")}
    if "mobile_device_id" not in cols:
        op.add_column(
            "user_devices",
            sa.Column("mobile_device_id", sa.String(length=128), nullable=True),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("user_devices")}
    if "ix_user_devices_mobile_device_id" not in indexes:
        op.create_index(
            "ix_user_devices_mobile_device_id",
            "user_devices",
            ["mobile_device_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("user_devices"):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("user_devices")}
    if "ix_user_devices_mobile_device_id" in indexes:
        op.drop_index("ix_user_devices_mobile_device_id", table_name="user_devices")
    cols = {c["name"] for c in inspector.get_columns("user_devices")}
    if "mobile_device_id" in cols:
        op.drop_column("user_devices", "mobile_device_id")
