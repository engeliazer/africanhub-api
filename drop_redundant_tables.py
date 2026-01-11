from database.db_connector import engine
from sqlalchemy import text

def drop_redundant_tables():
    with engine.connect() as conn:
        conn.execute(text('DROP TABLE IF EXISTS application_payments'))
        conn.execute(text('DROP TABLE IF EXISTS application_transactions'))
        conn.commit()
        print("Redundant tables dropped successfully")

if __name__ == "__main__":
    drop_redundant_tables() 