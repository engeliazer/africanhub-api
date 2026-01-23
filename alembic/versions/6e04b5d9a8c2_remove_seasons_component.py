"""remove seasons component

Revision ID: 6e04b5d9a8c2
Revises: 22ebba9f198e
Create Date: 2024-12-19 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6e04b5d9a8c2'
down_revision: Union[str, None] = '22ebba9f198e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, drop foreign key constraints that reference seasons
    # Drop foreign key from application_details.season_id
    # Find the constraint name dynamically
    connection = op.get_bind()
    
    # Get foreign key constraint name for application_details.season_id
    fk_query = """
        SELECT CONSTRAINT_NAME 
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
        WHERE TABLE_NAME = 'application_details' 
        AND COLUMN_NAME = 'season_id' 
        AND TABLE_SCHEMA = DATABASE()
    """
    result = connection.execute(sa.text(fk_query))
    fk_name = result.fetchone()
    if fk_name:
        op.drop_constraint(fk_name[0], 'application_details', type_='foreignkey')
    
    # Drop season_id column from application_details
    op.drop_column('application_details', 'season_id')
    
    # Drop season_applicants table
    op.drop_table('season_applicants')
    
    # Drop season_subjects table
    op.drop_table('season_subjects')
    
    # Drop seasons table
    op.drop_table('seasons')


def downgrade() -> None:
    # Recreate seasons table
    op.create_table('seasons',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(255), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    # Recreate season_subjects table
    op.create_table('season_subjects',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('season_id', sa.BigInteger(), nullable=False),
        sa.Column('subject_id', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season_id', 'subject_id', name='season_subject_unique')
    )
    
    # Recreate season_applicants table
    op.create_table('season_applicants',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('season_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'season_id', name='user_season_unique')
    )
    
    # Add season_id back to application_details (nullable initially)
    op.add_column('application_details', sa.Column('season_id', sa.BigInteger(), nullable=True))
    
    # Add foreign key constraint back
    op.create_foreign_key(
        'fk_application_details_season_id',
        'application_details', 'seasons',
        ['season_id'], ['id']
    )
    
    # Note: You would need to populate season_id data manually if downgrading
