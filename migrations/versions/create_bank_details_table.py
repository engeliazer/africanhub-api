"""create bank details table

Revision ID: create_bank_details_table
Revises: add_bank_reference_to_payments
Create Date: 2024-04-04 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_bank_details_table'
down_revision = 'add_bank_reference_to_payments'
branch_labels = None
depends_on = None

def upgrade():
    # Create bank_details table
    op.create_table(
        'bank_details',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('account_name', sa.String(100), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('branch_code', sa.String(20), nullable=False),
        sa.Column('swift_code', sa.String(20), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bank_details_id', 'bank_details', ['id'])

def downgrade():
    # Drop bank_details table
    op.drop_index('ix_bank_details_id', 'bank_details')
    op.drop_table('bank_details') 