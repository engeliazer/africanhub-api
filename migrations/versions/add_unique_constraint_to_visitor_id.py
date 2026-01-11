"""add unique constraint to visitor_id

Revision ID: add_unique_constraint_to_visitor_id
Revises: 724f8024c307
Create Date: 2024-04-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_unique_constraint_to_visitor_id'
down_revision = '724f8024c307'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # First, we need to handle duplicate visitor_ids
    # We'll keep the most recent record for each visitor_id
    op.execute("""
        DELETE t1 FROM user_devices t1
        INNER JOIN user_devices t2
        WHERE t1.visitor_id = t2.visitor_id
        AND t1.id < t2.id
    """)
    
    # Now add the unique constraint
    op.create_unique_constraint('uq_user_devices_visitor_id', 'user_devices', ['visitor_id'])

def downgrade() -> None:
    op.drop_constraint('uq_user_devices_visitor_id', 'user_devices', type_='unique') 