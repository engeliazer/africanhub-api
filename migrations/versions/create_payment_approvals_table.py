"""create payment approvals table

Revision ID: create_payment_approvals
Revises: create_bank_reconciliation_table
Create Date: 2024-03-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_payment_approvals'
down_revision = 'create_bank_reconciliation_table'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('payment_approvals',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('reconciliation_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('previous_status', sa.String(length=50), nullable=False),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['reconciliation_id'], ['bank_reconciliation.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('payment_approvals') 