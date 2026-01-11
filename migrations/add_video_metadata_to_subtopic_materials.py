import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connector import DBConnector
from sqlalchemy import text

def run_migration():
    db = DBConnector()
    session = db.get_session()
    try:
        # Add video_duration and file_size columns
        session.execute(text("""
            ALTER TABLE subtopic_materials 
            ADD COLUMN video_duration FLOAT,
            ADD COLUMN file_size BIGINT
        """))
        session.commit()
        print("Successfully added video_duration and file_size columns to subtopic_materials table")
    except Exception as e:
        session.rollback()
        print(f"Error during migration: {str(e)}")
        raise
    finally:
        db.close_session(session)

if __name__ == "__main__":
    run_migration() 