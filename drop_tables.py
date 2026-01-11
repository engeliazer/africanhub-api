from sqlalchemy import text
from database.db_connector import engine

def drop_tables():
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS chat_ratings"))
        connection.commit()
    print("Tables dropped successfully")

if __name__ == "__main__":
    drop_tables() 