"""Add public training registrations with pending status."""
from alembic import op
import sqlalchemy as sa

revision = "gd4e5f6a7b8c"
down_revision = "gc3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_training_registrations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("middle_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("organization", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.UniqueConstraint("event_id", "email", name="uq_event_training_registration_email"),
    )
    op.create_index("ix_event_training_registrations_id", "event_training_registrations", ["id"])
    op.create_index("ix_event_training_registrations_event_id", "event_training_registrations", ["event_id"])


def downgrade() -> None:
    op.drop_table("event_training_registrations")
