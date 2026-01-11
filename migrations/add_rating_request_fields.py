from sqlalchemy import text

def upgrade(engine):
    with engine.connect() as connection:
        connection.execute(text("""
            ALTER TABLE chat_ratings
            ADD COLUMN is_request BOOLEAN DEFAULT FALSE,
            ADD COLUMN requested_by BIGINT NULL,
            ADD COLUMN status VARCHAR(20) DEFAULT 'pending',
            ADD FOREIGN KEY (requested_by) REFERENCES users(id)
        """))
        connection.commit()

def downgrade(engine):
    with engine.connect() as connection:
        connection.execute(text("""
            ALTER TABLE chat_ratings
            DROP FOREIGN KEY chat_ratings_ibfk_2,
            DROP COLUMN is_request,
            DROP COLUMN requested_by,
            DROP COLUMN status
        """))
        connection.commit() 