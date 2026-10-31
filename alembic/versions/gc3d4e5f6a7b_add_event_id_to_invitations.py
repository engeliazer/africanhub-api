"""Associate special invitations with an event."""
from alembic import op
import sqlalchemy as sa

revision = "gc3d4e5f6a7b"
down_revision = "gb2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("event_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_invitations_event_id", "invitations", ["event_id"])
    op.create_foreign_key(
        "fk_invitations_event_id_events", "invitations", "events", ["event_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_invitations_event_id_events", "invitations", type_="foreignkey")
    op.drop_index("ix_invitations_event_id", table_name="invitations")
    op.drop_column("invitations", "event_id")
