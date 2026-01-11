"""add batch_id to bank transactions

Revision ID: add_batch_id_to_bank_transactions
Revises: create_bank_transactions_table
Create Date: 2024-04-04 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_batch_id_to_bank_transactions'
down_revision = 'create_bank_transactions_table'
branch_labels = None
depends_on = None

def upgrade():
    # Create bank_statement_batches table first
    op.create_table(
        'bank_statement_batches',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('account_id', sa.BigInteger(), nullable=False),
        sa.Column('batch_reference', sa.String(50), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('number_of_transactions', sa.Integer(), nullable=False),
        sa.Column('total_batch_amount', sa.Float(), nullable=False),
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
    op.create_index('ix_bank_statement_batches_id', 'bank_statement_batches', ['id'])
    op.create_index('ix_bank_statement_batches_batch_reference', 'bank_statement_batches', ['batch_reference'], unique=True)

    # Add batch_id column to bank_transactions table
    op.add_column('bank_transactions', sa.Column('batch_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        'fk_bank_transactions_batch_id',
        'bank_transactions', 'bank_statement_batches',
        ['batch_id'], ['id']
    )

def downgrade():
    # Remove batch_id column from bank_transactions table
    op.drop_constraint('fk_bank_transactions_batch_id', 'bank_transactions', type_='foreignkey')
    op.drop_column('bank_transactions', 'batch_id')

    # Drop bank_statement_batches table
    op.drop_index('ix_bank_statement_batches_batch_reference', 'bank_statement_batches')
    op.drop_index('ix_bank_statement_batches_id', 'bank_statement_batches')
    op.drop_table('bank_statement_batches') 