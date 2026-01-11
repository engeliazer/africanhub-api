from sqlalchemy import text

def upgrade(connection):
    # Check if deleted_at exists in chats
    result = connection.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = 'chats' 
        AND column_name = 'deleted_at'
    """)).scalar()
    
    if result == 0:
        connection.execute(text("""
            ALTER TABLE chats
            ADD COLUMN deleted_at DATETIME NULL;
        """))

def downgrade(connection):
    connection.execute(text("""
        ALTER TABLE chats
        DROP COLUMN IF EXISTS deleted_at;
    """)) 