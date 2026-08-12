from .db_connector import DBConnector

# Global connector — do NOT run DDL here; app startup calls init_db() explicitly.
db = DBConnector()
