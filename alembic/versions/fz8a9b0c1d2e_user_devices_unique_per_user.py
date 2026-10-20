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
    # MySQL: global unique on visitor_id is typically index name `visitor_id`
    for stmt in (
        "ALTER TABLE user_devices DROP INDEX visitor_id",
        "ALTER TABLE user_devices DROP INDEX uq_user_devices_visitor_id",
    ):
        try:
            op.execute(stmt)
        except Exception:
            pass

    op.execute(
        "ALTER TABLE user_devices ADD UNIQUE KEY uq_user_devices_user_id_visitor_id "
        "(user_id, visitor_id)"
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
