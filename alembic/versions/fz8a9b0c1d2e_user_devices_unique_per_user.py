"""user_devices: unique (user_id, visitor_id) instead of global visitor_id

Revision ID: fz8a9b0c1d2e
Revises: fy7e8f9a0b1c
Create Date: 2026-10-19

"""
from alembic import op

revision = "fz8a9b0c1d2e"
down_revision = "fy7e8f9a0b1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for index_name in ("uq_user_devices_visitor_id", "visitor_id"):
        try:
            op.drop_index(index_name, table_name="user_devices")
        except Exception:
            try:
                op.drop_constraint(index_name, "user_devices", type_="unique")
            except Exception:
                pass

    op.create_unique_constraint(
        "uq_user_devices_user_id_visitor_id",
        "user_devices",
        ["user_id", "visitor_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_devices_user_id_visitor_id",
        "user_devices",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_user_devices_visitor_id",
        "user_devices",
        ["visitor_id"],
    )
