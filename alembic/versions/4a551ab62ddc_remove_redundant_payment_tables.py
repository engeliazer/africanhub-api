"""remove_redundant_payment_tables

Revision ID: 4a551ab62ddc
Revises: 724f8024c307
Create Date: 2025-04-13 14:23:44.856266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a551ab62ddc'
down_revision: Union[str, None] = '724f8024c307'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the redundant tables
    op.drop_table('application_payments')
    op.drop_table('application_transactions')


def downgrade() -> None:
    # Recreate the tables if needed to roll back
    op.create_table(
        'application_payments',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('application_id', sa.BigInteger(), nullable=False),
        sa.Column('payment_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'application_transactions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('application_id', sa.BigInteger(), nullable=False),
        sa.Column('transaction_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['payment_transactions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
