from sqlalchemy import text

def upgrade(engine):
    with engine.connect() as connection:
        connection.execute(text("""
            ALTER TABLE chat_ratings
            MODIFY COLUMN rating FLOAT NULL;
        """))
        connection.commit()

def downgrade(engine):
    with engine.connect() as connection:
        connection.execute(text("""
            ALTER TABLE chat_ratings
            MODIFY COLUMN rating FLOAT NOT NULL;
        """))
        connection.commit() 