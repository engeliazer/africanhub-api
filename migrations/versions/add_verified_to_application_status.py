"""add verified to application status

Revision ID: add_verified_to_application_status
Revises: 4a551ab62ddc
Create Date: 2024-04-14 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'add_verified_to_application_status'
down_revision = '4a551ab62ddc'
branch_labels = None
depends_on = None

def upgrade():
    # Create new enum with 'verified' status
    op.execute("ALTER TABLE applications MODIFY COLUMN status ENUM('pending', 'approved', 'rejected', 'waitlisted', 'withdrawn', 'verified')")

def downgrade():
    # Remove 'verified' from enum
    op.execute("ALTER TABLE applications MODIFY COLUMN status ENUM('pending', 'approved', 'rejected', 'waitlisted', 'withdrawn')") 