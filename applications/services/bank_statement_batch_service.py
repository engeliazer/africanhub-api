from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime

from applications.models.models import BankStatementBatch, BankTransaction, BankDetails
from applications.schemas.bank_statement_batch import (
    BankStatementBatchCreate,
    BankStatementBatchUpdate,
    BankTransactionCreate
)

class BankStatementBatchService:
    def __init__(self, db: Session):
        self.db = db

    def create_batch(self, batch_data: BankStatementBatchCreate, user_id: int) -> BankStatementBatch:
        """Create a new bank statement batch with transactions"""
        try:
            # Verify bank account exists
            bank_account = (
                self.db.query(BankDetails)
                .filter(BankDetails.id == batch_data.account_id)
                .filter(BankDetails.is_active == True)
                .first()
            )
            if not bank_account:
                raise HTTPException(status_code=404, detail="Bank account not found")

            # Create batch
            batch = BankStatementBatch(
                account_id=batch_data.account_id,
                batch_reference=batch_data.batch_reference,
                start_date=batch_data.start_date,
                end_date=batch_data.end_date,
                number_of_transactions=batch_data.number_of_transactions,
                total_batch_amount=batch_data.total_batch_amount,
                created_by=user_id,
                updated_by=user_id
            )
            self.db.add(batch)
            self.db.flush()  # Get batch ID without committing

            # Process transactions
            for transaction_data in batch_data.transactions:
                # Check for existing transaction
                existing_transaction = (
                    self.db.query(BankTransaction)
                    .filter(BankTransaction.transaction_id == transaction_data.transaction_id)
                    .first()
                )
                if existing_transaction:
                    continue  # Skip if transaction already exists

                # Create new transaction
                transaction = BankTransaction(
                    account_id=batch_data.account_id,
                    batch_id=batch.id,
                    transaction_id=transaction_data.transaction_id,
                    payment_date=transaction_data.payment_date,
                    reference_number=transaction_data.reference_number,
                    account_number=transaction_data.account_number,
                    amount=transaction_data.amount,
                    created_by=user_id,
                    updated_by=user_id
                )
                self.db.add(transaction)

            self.db.commit()
            return batch

        except IntegrityError as e:
            self.db.rollback()
            raise HTTPException(status_code=400, detail="Duplicate batch reference or transaction ID")
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def get_batch(self, batch_id: int) -> BankStatementBatch:
        """Get a bank statement batch by ID"""
        batch = (
            self.db.query(BankStatementBatch)
            .filter(BankStatementBatch.id == batch_id)
            .first()
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Bank statement batch not found")
        return batch

    def get_batches_by_account(self, account_id: int) -> List[BankStatementBatch]:
        """Get all bank statement batches for an account"""
        return (
            self.db.query(BankStatementBatch)
            .filter(BankStatementBatch.account_id == account_id)
            .filter(BankStatementBatch.is_active == True)
            .all()
        )

    def update_batch(self, batch_id: int, batch_data: BankStatementBatchUpdate, user_id: int) -> BankStatementBatch:
        """Update a bank statement batch"""
        batch = self.get_batch(batch_id)
        
        # Update fields if provided
        for field, value in batch_data.dict(exclude_unset=True).items():
            setattr(batch, field, value)
        
        batch.updated_by = user_id
        batch.updated_at = datetime.utcnow()
        
        try:
            self.db.commit()
            return batch
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=400, detail="Duplicate batch reference")
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def delete_batch(self, batch_id: int, user_id: int) -> None:
        """Soft delete a bank statement batch"""
        batch = self.get_batch(batch_id)
        batch.is_active = False
        batch.updated_by = user_id
        batch.updated_at = datetime.utcnow()
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e)) 