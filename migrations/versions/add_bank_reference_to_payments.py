"""add bank reference to payments

Revision ID: add_bank_reference_to_payments
Revises: 
Create Date: 2024-04-04 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_bank_reference_to_payments'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add bank_reference column to payments table
    op.add_column('payments', sa.Column('bank_reference', sa.String(50), nullable=True))

def downgrade():
    # Remove bank_reference column from payments table
    op.drop_column('payments', 'bank_reference') 