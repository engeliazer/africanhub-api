"""Add deleted_at column to study_material_categories table"""
from sqlalchemy import text

def upgrade(connection):
    # Check if column exists
    result = connection.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = 'study_material_categories' 
        AND column_name = 'deleted_at'
    """))
    
    if result.scalar() == 0:
        connection.execute(text("""
            ALTER TABLE study_material_categories 
            ADD COLUMN deleted_at TIMESTAMP NULL
        """))

def downgrade(connection):
    connection.execute(text("""
        ALTER TABLE study_material_categories 
        DROP COLUMN IF EXISTS deleted_at
    """)) 