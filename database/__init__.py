from .db_connector import DBConnector

# Create a global database connector instance
db = DBConnector()

# Initialize the database
db.create_all_tables() 