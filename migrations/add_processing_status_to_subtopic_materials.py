"""add processing status to subtopic materials

Revision ID: add_processing_status
Revises: 
Create Date: 2024-06-13 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_processing_status'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add processing status columns
    op.add_column('subtopic_materials', sa.Column('processing_status', sa.String(20), server_default='pending'))
    op.add_column('subtopic_materials', sa.Column('processing_progress', sa.Integer(), server_default='0'))
    op.add_column('subtopic_materials', sa.Column('processing_error', sa.Text(), nullable=True))

def downgrade():
    # Remove processing status columns
    op.drop_column('subtopic_materials', 'processing_status')
    op.drop_column('subtopic_materials', 'processing_progress')
    op.drop_column('subtopic_materials', 'processing_error') 