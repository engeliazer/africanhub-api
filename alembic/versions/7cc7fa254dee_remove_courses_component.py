"""remove courses component

Revision ID: 7cc7fa254dee
Revises: 724f8024c307
Create Date: 2024-12-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '7cc7fa254dee'
down_revision: Union[str, None] = '724f8024c307'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop foreign key constraint from subjects.course_id
    op.drop_constraint('subjects_ibfk_1', 'subjects', type_='foreignkey')
    
    # Drop the course_id column from subjects table
    op.drop_column('subjects', 'course_id')
    
    # Drop the courses table
    op.drop_table('courses')


def downgrade() -> None:
    # Recreate courses table
    op.create_table(
        'courses',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_courses_id', 'courses', ['id'])
    
    # Add course_id column back to subjects (nullable first)
    op.add_column('subjects', sa.Column('course_id', sa.BigInteger(), nullable=True))
    
    # Create a default course for existing subjects
    connection = op.get_bind()
    connection.execute("""
        INSERT INTO courses (name, code, description, is_active, created_by, updated_by)
        VALUES ('Default Course', 'DEFAULT', 'Default course for migrated subjects', 1, 1, 1)
        WHERE NOT EXISTS (SELECT 1 FROM courses WHERE code = 'DEFAULT')
    """)
    
    # Update existing subjects to use the default course
    connection.execute("""
        UPDATE subjects
        SET course_id = (SELECT id FROM courses WHERE code = 'DEFAULT')
        WHERE course_id IS NULL
    """)
    
    # Make course_id non-nullable after updating existing records
    op.alter_column('subjects', 'course_id',
                   existing_type=sa.BigInteger(),
                   nullable=False)
    
    # Recreate foreign key constraint
    op.create_foreign_key('subjects_ibfk_1', 'subjects', 'courses', ['course_id'], ['id'], ondelete='CASCADE')

