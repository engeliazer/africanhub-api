from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database connection details from environment variables
DB_USER = os.getenv('DB_USER', 'ocpac')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ocpac')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'ocpac')

# Create database connection
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def check_and_fix_table():
    with engine.connect() as connection:
        # Check if columns exist
        result = connection.execute(text("SHOW COLUMNS FROM subtopic_materials"))
        columns = [row[0] for row in result]
        
        print("Current columns:", columns)
        
        # Add missing columns if they don't exist
        if 'processing_status' not in columns:
            print("Adding processing_status column...")
            connection.execute(text("""
                ALTER TABLE subtopic_materials
                ADD COLUMN processing_status VARCHAR(20) DEFAULT 'pending'
            """))
        
        if 'processing_progress' not in columns:
            print("Adding processing_progress column...")
            connection.execute(text("""
                ALTER TABLE subtopic_materials
                ADD COLUMN processing_progress INTEGER DEFAULT 0
            """))
        
        if 'processing_error' not in columns:
            print("Adding processing_error column...")
            connection.execute(text("""
                ALTER TABLE subtopic_materials
                ADD COLUMN processing_error TEXT
            """))
        
        # Verify the changes
        result = connection.execute(text("SHOW COLUMNS FROM subtopic_materials"))
        columns = [row[0] for row in result]
        print("\nUpdated columns:", columns)

if __name__ == "__main__":
    check_and_fix_table() 