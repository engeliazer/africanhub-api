import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connector import engine
from sqlalchemy import text

def run_sql_migration():
    with engine.connect() as connection:
        with open('migrations/add_bank_reference.sql', 'r') as file:
            sql = file.read()
            connection.execute(text(sql))
            connection.commit()

if __name__ == '__main__':
    run_sql_migration() 