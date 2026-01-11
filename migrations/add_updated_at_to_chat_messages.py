from sqlalchemy import text

def upgrade(connection):
    # Check if updated_at exists in chat_messages
    result = connection.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = 'chat_messages' 
        AND column_name = 'updated_at'
    """)).scalar()
    
    if result == 0:
        connection.execute(text("""
            ALTER TABLE chat_messages
            ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
        """))
    
    # Check if updated_at exists in chat_ratings
    result = connection.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = 'chat_ratings' 
        AND column_name = 'updated_at'
    """)).scalar()
    
    if result == 0:
        connection.execute(text("""
            ALTER TABLE chat_ratings
            ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
        """))

def downgrade(connection):
    connection.execute(text("""
        ALTER TABLE chat_messages
        DROP COLUMN IF EXISTS updated_at;
        
        ALTER TABLE chat_ratings
        DROP COLUMN IF EXISTS updated_at;
    """)) 