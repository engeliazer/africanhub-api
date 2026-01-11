import os
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from database.db_connector import DBConnector
from create_sub_topics_table import upgrade

def run_migrations():
    db = DBConnector()
    session = db.get_session()
    try:
        upgrade(session)
        print("Migration completed successfully")
    except Exception as e:
        print(f"Error running migration: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_migrations() 