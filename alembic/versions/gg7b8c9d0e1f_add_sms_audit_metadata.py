"""Add SMS recipient names, category and optional batch reference."""
from alembic import op
import sqlalchemy as sa

revision = 'gg7b8c9d0e1f'
down_revision = 'gf6a7b8c9d0e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sms_logs', sa.Column('recipient_name', sa.String(255), nullable=True))
    # Unknown historical categories stay NULL rather than assigning an inaccurate category.
    op.add_column('sms_logs', sa.Column('category', sa.String(10), nullable=True))
    op.add_column('sms_logs', sa.Column('batch_name', sa.String(255), nullable=True))
    op.execute("UPDATE sms_logs SET category = 'bulk' WHERE process_name IN ('batch', 'api_send_batch', 'broadcast', 'custom')")
    op.execute("UPDATE sms_logs SET category = 'single' WHERE process_name IN ('registration', 'password_reset', 'api_send', 'test_sms')")
    op.create_index('ix_sms_logs_category', 'sms_logs', ['category'])
    op.create_index('ix_sms_logs_batch_name', 'sms_logs', ['batch_name'])


def downgrade():
    op.drop_index('ix_sms_logs_batch_name', table_name='sms_logs')
    op.drop_index('ix_sms_logs_category', table_name='sms_logs')
    op.drop_column('sms_logs', 'batch_name')
    op.drop_column('sms_logs', 'category')
    op.drop_column('sms_logs', 'recipient_name')
