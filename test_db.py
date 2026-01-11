"""
Test script to directly check application statuses in the database
"""
from sqlalchemy import text
from database.db_connector import db_session

def test_applications_in_db():
    """Test retrieving applications directly from database"""
    try:
        # Execute a direct SQL query to get all applications
        result = db_session.execute(text("SELECT id, status, payment_status FROM applications"))
        
        print("Applications in the database:")
        for row in result:
            print(f"ID: {row[0]}, Status: {row[1]}, Payment Status: {row[2]}")
        
        # Count applications by status
        result = db_session.execute(text("SELECT status, COUNT(*) FROM applications GROUP BY status"))
        print("\nApplication counts by status:")
        for row in result:
            print(f"Status: {row[0]}, Count: {row[1]}")
        
        # Count applications by payment status
        result = db_session.execute(text("SELECT payment_status, COUNT(*) FROM applications GROUP BY payment_status"))
        print("\nApplication counts by payment status:")
        for row in result:
            print(f"Payment Status: {row[0]}, Count: {row[1]}")
    finally:
        db_session.remove()

if __name__ == "__main__":
    test_applications_in_db() 