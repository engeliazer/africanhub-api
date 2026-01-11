import os
from dotenv import load_dotenv
import importlib.util
import sys
from database.db_connector import DBConnector
from sqlalchemy import text

# Load environment variables
load_dotenv()

def run_migrations():
    # Initialize database connection
    db = DBConnector()
    
    migrations_dir = "migrations"
    
    # Get all Python files in the migrations directory
    migration_files = [f for f in os.listdir(migrations_dir) 
                      if f.endswith('.py') and f != '__init__.py']
    
    # Sort migration files to ensure consistent order
    migration_files.sort()
    
    # Get database connection
    connection = db.get_engine().connect()
    
    for migration_file in migration_files:
        try:
            # Get the full path of the migration file
            file_path = os.path.join(migrations_dir, migration_file)
            
            # Load the migration module
            spec = importlib.util.spec_from_file_location(
                migration_file[:-3], file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Run the upgrade function with the connection
            with connection.begin():
                module.upgrade(connection)
            
            print(f"Successfully ran migration: {migration_file}")
            
        except Exception as e:
            print(f"Error running migration {migration_file}: {str(e)}")
            sys.exit(1)
    
    # Close the connection
    connection.close()

if __name__ == "__main__":
    run_migrations() 