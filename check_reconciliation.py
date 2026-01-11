from database.db_connector import DBConnector
from sqlalchemy import text

def check_reconciliation():
    # Initialize database connection
    db = DBConnector()
    session = db.get_session()
    
    try:
        # Check if table exists
        result = session.execute(text("SHOW TABLES LIKE 'bank_reconciliation'"))
        table_exists = result.fetchone() is not None
        
        if not table_exists:
            print("bank_reconciliation table does not exist!")
            return
        
        # Count total records
        result = session.execute(text("SELECT COUNT(*) FROM bank_reconciliation"))
        total_records = result.scalar()
        print(f"\nTotal bank reconciliation records: {total_records}")
        
        if total_records > 0:
            # Get all reconciliation records with related data
            query = """
                SELECT 
                    br.id as reconciliation_id,
                    br.payment_id,
                    br.bank_transaction_id,
                    br.status,
                    bt.reference_number,
                    p.amount as payment_amount,
                    bt.amount as transaction_amount
                FROM bank_reconciliation br
                JOIN bank_transactions bt ON br.bank_transaction_id = bt.id
                JOIN payments p ON br.payment_id = p.id
            """
            result = session.execute(text(query))
            records = result.fetchall()
            
            print("\nReconciliation Records:")
            print("-" * 80)
            for record in records:
                print(f"Reconciliation ID: {record.reconciliation_id}")
                print(f"Payment ID: {record.payment_id}")
                print(f"Bank Transaction ID: {record.bank_transaction_id}")
                print(f"Status: {record.status}")
                print(f"Bank Reference: {record.reference_number}")
                print(f"Payment Amount: {record.payment_amount}")
                print(f"Transaction Amount: {record.transaction_amount}")
                print("-" * 80)
        else:
            print("No reconciliation records found in the database.")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    check_reconciliation() 