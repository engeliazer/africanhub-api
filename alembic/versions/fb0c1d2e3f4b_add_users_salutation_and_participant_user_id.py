"""add users.salutation_id and certificate_participants.user_id

Revision ID: fb0c1d2e3f4b
Revises: fa0c1d2e3f4a
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "fb0c1d2e3f4b"
down_revision: Union[str, None] = "fa0c1d2e3f4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    user_columns = {col["name"] for col in inspector.get_columns("users")}

    if "salutation_id" not in user_columns:
        op.add_column("users", sa.Column("salutation_id", sa.BigInteger(), nullable=True))
        op.create_index("idx_users_salutation_id", "users", ["salutation_id"])

    if inspector.has_table("certificate_participants"):
        participant_columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
        if "user_id" not in participant_columns:
            if "full_name" in participant_columns:
                op.add_column("certificate_participants", sa.Column("user_id", sa.BigInteger(), nullable=True))
                if "salutation_id" in participant_columns:
                    op.drop_constraint(
                        "fk_certificate_participants_salutation",
                        "certificate_participants",
                        type_="foreignkey",
                    )
                    op.drop_index(
                        "idx_certificate_participants_salutation",
                        table_name="certificate_participants",
                    )
                    op.drop_column("certificate_participants", "salutation_id")
                op.drop_column("certificate_participants", "full_name")
                op.alter_column("certificate_participants", "user_id", nullable=False)
            else:
                op.add_column(
                    "certificate_participants",
                    sa.Column("user_id", sa.BigInteger(), nullable=False),
                )
            op.create_index(
                "idx_certificate_participants_user",
                "certificate_participants",
                ["user_id"],
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("certificate_participants"):
        participant_columns = {col["name"] for col in inspector.get_columns("certificate_participants")}
        if "user_id" in participant_columns:
            op.drop_index("idx_certificate_participants_user", table_name="certificate_participants")
            op.drop_column("certificate_participants", "user_id")
            op.add_column("certificate_participants", sa.Column("full_name", sa.String(255), nullable=False))
            op.add_column("certificate_participants", sa.Column("salutation_id", sa.BigInteger(), nullable=False))

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "salutation_id" in user_columns:
        op.drop_index("idx_users_salutation_id", table_name="users")
        op.drop_column("users", "salutation_id")
