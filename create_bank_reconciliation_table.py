from database.db_connector import engine
from sqlalchemy import text

def create_bank_reconciliation_table():
    with engine.connect() as conn:
        # Create bank_reconciliation table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bank_reconciliation (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                bank_transaction_id BIGINT NOT NULL,
                payment_id BIGINT NOT NULL,
                status ENUM('matched', 'verified', 'approved', 'rejected') NOT NULL DEFAULT 'matched',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_by BIGINT,
                updated_by BIGINT,
                deleted_by BIGINT,
                deleted_at DATETIME,
                FOREIGN KEY (bank_transaction_id) REFERENCES bank_transactions(id),
                FOREIGN KEY (payment_id) REFERENCES payments(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (updated_by) REFERENCES users(id),
                FOREIGN KEY (deleted_by) REFERENCES users(id)
            )
        """))
        conn.commit()
        print("Created bank_reconciliation table")

if __name__ == "__main__":
    create_bank_reconciliation_table() 