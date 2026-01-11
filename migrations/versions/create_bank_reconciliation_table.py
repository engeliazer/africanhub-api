"""create bank reconciliation table

Revision ID: create_bank_reconciliation_table
Revises: add_bank_reference_to_payments
Create Date: 2024-03-12 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_bank_reconciliation_table'
down_revision = 'add_bank_reference_to_payments'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('bank_reconciliation',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('payment_id', sa.BigInteger(), nullable=False),
        sa.Column('bank_transaction_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['bank_transaction_id'], ['bank_transactions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('bank_reconciliation') 