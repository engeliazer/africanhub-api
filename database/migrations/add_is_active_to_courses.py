from sqlalchemy import text
from database.db_connector import db_session

def upgrade():
    # Add is_active column to courses table
    db_session.execute(text("""
        ALTER TABLE courses
        ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE
    """))
    db_session.commit()

def downgrade():
    # Remove is_active column from courses table
    db_session.execute(text("""
        ALTER TABLE courses
        DROP COLUMN is_active
    """))
    db_session.commit() 