"""create bank transactions table

Revision ID: create_bank_transactions_table
Revises: create_bank_details_table
Create Date: 2024-04-13 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'create_bank_transactions_table'
down_revision: Union[str, None] = 'create_bank_details_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create bank_transactions table
    op.create_table(
        'bank_transactions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('account_id', sa.BigInteger(), nullable=False),
        sa.Column('transaction_id', sa.String(50), nullable=False),
        sa.Column('payment_date', sa.DateTime(), nullable=False),
        sa.Column('reference_number', sa.String(50), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['bank_details.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bank_transactions_id', 'bank_transactions', ['id'])
    op.create_index('ix_bank_transactions_transaction_id', 'bank_transactions', ['transaction_id'], unique=True)


def downgrade() -> None:
    # Drop bank_transactions table
    op.drop_index('ix_bank_transactions_transaction_id', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_id', table_name='bank_transactions')
    op.drop_table('bank_transactions') 