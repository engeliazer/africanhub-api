"""add event payment fields and trainer assignments

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("events"):
        existing = {c["name"] for c in inspector.get_columns("events")}
        if "course_fee" not in existing:
            op.add_column("events", sa.Column("course_fee", sa.Numeric(12, 2), nullable=True))
        if "deposit_amount" not in existing:
            op.add_column("events", sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=True))
        if "reservation_deadline" not in existing:
            op.add_column("events", sa.Column("reservation_deadline", sa.Date(), nullable=True))
        if "bank_account_name" not in existing:
            op.add_column("events", sa.Column("bank_account_name", sa.String(255), nullable=True))
        if "bank_account_number" not in existing:
            op.add_column("events", sa.Column("bank_account_number", sa.String(100), nullable=True))
        if "bank_name" not in existing:
            op.add_column("events", sa.Column("bank_name", sa.String(255), nullable=True))

    if not inspector.has_table("event_trainer_assignments"):
        op.create_table(
            "event_trainer_assignments",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("event_id", sa.BigInteger(), nullable=False),
            sa.Column("trainer_id", sa.BigInteger(), nullable=False),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["trainer_id"], ["invitation_trainers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_event_trainer_assignments_id", "event_trainer_assignments", ["id"])
        op.create_index("ix_event_trainer_assignments_event_id", "event_trainer_assignments", ["event_id"])
        op.create_index("ix_event_trainer_assignments_trainer_id", "event_trainer_assignments", ["trainer_id"])


def downgrade() -> None:
    op.drop_index("ix_event_trainer_assignments_trainer_id", table_name="event_trainer_assignments")
    op.drop_index("ix_event_trainer_assignments_event_id", table_name="event_trainer_assignments")
    op.drop_index("ix_event_trainer_assignments_id", table_name="event_trainer_assignments")
    op.drop_table("event_trainer_assignments")
    op.drop_column("events", "bank_name")
    op.drop_column("events", "bank_account_number")
    op.drop_column("events", "bank_account_name")
    op.drop_column("events", "reservation_deadline")
    op.drop_column("events", "deposit_amount")
    op.drop_column("events", "course_fee")
