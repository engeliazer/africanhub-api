"""add_deleted_at_to_subjects

Revision ID: db65030c23bb
Revises: 
Create Date: 2025-04-09 16:17:31.256499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db65030c23bb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add deleted_at column to subjects table
    op.add_column('subjects', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove deleted_at column from subjects table
    op.drop_column('subjects', 'deleted_at')
