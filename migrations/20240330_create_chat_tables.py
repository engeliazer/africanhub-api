from sqlalchemy import text

def upgrade(connection):
    # Add is_admin column to users table if it doesn't exist
    result = connection.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'is_admin'
    """)).scalar()
    
    if result == 0:
        connection.execute(text("""
            ALTER TABLE users 
            ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0
        """))

    # Create chats table
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS chats (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """))

    # Create chat_messages table
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            chat_id BIGINT NOT NULL,
            sender_id BIGINT NOT NULL,
            message TEXT NOT NULL,
            is_from_user BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """))

def downgrade(connection):
    # Drop tables in reverse order
    connection.execute(text("DROP TABLE IF EXISTS chat_messages"))
    connection.execute(text("DROP TABLE IF EXISTS chats"))
    connection.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_admin")) 