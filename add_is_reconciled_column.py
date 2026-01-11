from database.db_connector import engine
from sqlalchemy import text

def add_is_reconciled_column():
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'bank_transactions' 
            AND column_name = 'is_reconciled'
        """))
        column_exists = result.scalar() > 0
        
        if not column_exists:
            # Add is_reconciled column
            conn.execute(text("""
                ALTER TABLE bank_transactions 
                ADD COLUMN is_reconciled BOOLEAN NOT NULL DEFAULT FALSE
            """))
            conn.commit()
            print("Added is_reconciled column to bank_transactions table")
        else:
            print("is_reconciled column already exists in bank_transactions table")

if __name__ == "__main__":
    add_is_reconciled_column() 