import os
import sys
from dotenv import load_dotenv
from database.db_connector import db_session, init_db

def run_migrations():
    # Load environment variables
    load_dotenv()
    
    # Initialize database connection
    init_db()
    
    # Get all migration files in the migrations directory
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    migration_files = [f for f in os.listdir(migrations_dir) 
                      if f.endswith('.py') 
                      and f != 'run_migrations.py'
                      and f != '__init__.py']
    
    # Sort migration files to ensure they run in order
    migration_files.sort()
    
    for migration_file in migration_files:
        print(f"Running migration: {migration_file}")
        try:
            # Import the migration module
            module_name = f"database.migrations.{os.path.splitext(migration_file)[0]}"
            migration_module = __import__(module_name, fromlist=['upgrade'])
            
            # Run the upgrade function
            migration_module.upgrade()
            print(f"Successfully ran migration: {migration_file}")
        except Exception as e:
            print(f"Error running migration {migration_file}: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    run_migrations() 