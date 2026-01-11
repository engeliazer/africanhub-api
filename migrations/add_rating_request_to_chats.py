from sqlalchemy import text

def upgrade(connection):
    connection.execute(text("""
        ALTER TABLE chats
        ADD COLUMN rating_requested_at DATETIME NULL,
        ADD COLUMN rating_requested_by BIGINT NULL,
        ADD FOREIGN KEY (rating_requested_by) REFERENCES users(id)
    """))
    connection.commit()

def downgrade(connection):
    connection.execute(text("""
        ALTER TABLE chats
        DROP FOREIGN KEY chats_ibfk_2,
        DROP COLUMN rating_requested_at,
        DROP COLUMN rating_requested_by
    """))
    connection.commit() 