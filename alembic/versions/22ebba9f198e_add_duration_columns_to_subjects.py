"""add duration columns to subjects

Revision ID: 22ebba9f198e
Revises: 7cc7fa254dee
Create Date: 2024-12-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '22ebba9f198e'
down_revision: Union[str, None] = '7cc7fa254dee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add duration_days column to subjects table
    op.add_column('subjects', sa.Column('duration_days', sa.Integer(), nullable=True, comment='Standard access duration in days'))
    
    # Add trial_duration_days column to subjects table
    op.add_column('subjects', sa.Column('trial_duration_days', sa.Integer(), nullable=True, comment='Trial period duration in days'))


def downgrade() -> None:
    # Remove the duration columns
    op.drop_column('subjects', 'trial_duration_days')
    op.drop_column('subjects', 'duration_days')
