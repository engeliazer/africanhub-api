"""create payment methods table

Revision ID: create_payment_methods_table
Revises: 4a551ab62ddc
Create Date: 2024-04-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_payment_methods_table'
down_revision = '4a551ab62ddc'
branch_labels = None
depends_on = None

def upgrade():
    # Create payment_methods table
    op.create_table(
        'payment_methods',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('icon', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_payment_methods_code')
    )
    op.create_index('ix_payment_methods_id', 'payment_methods', ['id'])

    # Insert existing payment methods
    op.execute("""
        INSERT INTO payment_methods (name, code, icon, description, instructions, is_active, created_at, updated_at)
        VALUES 
        ('M-Pesa', 'M-Pesa', '/mnos/m-pesa.png', 'Pay using M-Pesa mobile money', 'Enter your mobile number to receive payment instructions', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('Mixx by Yas', 'Mixx by Yas', '/mnos/mixx-yas.png', 'Pay using Mixx by Yas mobile money', 'Enter your mobile number to receive payment instructions', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('Airtel Money', 'Airtel Money', '/mnos/airtel-money.png', 'Pay using Airtel Money mobile money', 'Enter your mobile number to receive payment instructions', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('Bank', 'Bank', '/mnos/bank.png', 'Pay using bank transfer', 'Use the provided bank details to make a transfer', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('Card', 'Card', '/mnos/card.png', 'Pay using credit/debit card', 'Enter your card details to complete the payment', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('Cash', 'Cash', '/mnos/cash.png', 'Pay using cash', 'Visit our office to make the payment in cash', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('Other', 'Other', '/mnos/other.png', 'Other payment methods', 'Contact our support for alternative payment methods', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)

def downgrade():
    op.drop_table('payment_methods') 