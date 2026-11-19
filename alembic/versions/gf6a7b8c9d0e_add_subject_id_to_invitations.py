"""Associate special invitations with a subject."""
from alembic import op
import sqlalchemy as sa

revision = "gf6a7b8c9d0e"
down_revision = "ge5f6a7b8c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("subject_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_invitations_subject_id", "invitations", ["subject_id"])
    op.create_foreign_key(
        "fk_invitations_subject_id_subjects", "invitations", "subjects", ["subject_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_invitations_subject_id_subjects", "invitations", type_="foreignkey")
    op.drop_index("ix_invitations_subject_id", table_name="invitations")
    op.drop_column("invitations", "subject_id")
