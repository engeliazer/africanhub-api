from app import app
from database.db_connector import init_db

# Initialize the database
init_db()

if __name__ == "__main__":
    app.run() 