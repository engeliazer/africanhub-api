from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from applications.models.models import BankTransaction, BankStatementBatch
from database.db_connector import get_db
from applications.schemas.bank_statement_batch import (
    BankStatementBatchCreate,
    BankStatementBatchResponse,
    BankTransactionCreate
)

router = APIRouter(prefix="/api/bank-statement-batches", tags=["bank-statement-batches"])

@router.post("/test/upload", status_code=status.HTTP_201_CREATED)
async def test_upload_bank_statement(
    data: dict,
    db: Session = Depends(get_db)
):
    """Test endpoint for uploading bank statement transactions (no JWT required)"""
    try:
        # Extract the nested transactions data
        transactions_data = data.get('transactions', {})
        account_id = transactions_data.get('account_id')
        transactions = transactions_data.get('transactions', [])
        batch_details = transactions_data.get('batch_details', {})
        
        if not account_id or not transactions or not batch_details:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Missing required fields: account_id, transactions, or batch_details'
            )
        
        # Create the batch first
        batch = BankStatementBatch(
            account_id=int(account_id),
            batch_reference=batch_details.get('batch_reference'),
            start_date=datetime.strptime(batch_details.get('start_date'), '%Y-%m-%d'),
            end_date=datetime.strptime(batch_details.get('end_date'), '%Y-%m-%d'),
            number_of_transactions=batch_details.get('number_of_transactions'),
            total_batch_amount=float(batch_details.get('total_batch_amount')),
            created_by=1,  # Dummy user ID for test
            updated_by=1   # Dummy user ID for test
        )
        
        db.add(batch)
        db.flush()  # Get the batch ID without committing
        
        # Process each transaction
        processed_transactions = []
        for transaction in transactions:
            # Check if transaction already exists
            existing_transaction = (
                db.query(BankTransaction)
                .filter(BankTransaction.transaction_id == transaction['transaction_id'])
                .first()
            )
            
            if existing_transaction:
                continue  # Skip if transaction already exists
            
            # Create new transaction with batch_id
            new_transaction = BankTransaction(
                account_id=int(account_id),
                batch_id=batch.id,  # Link to the batch
                transaction_id=transaction['transaction_id'],
                payment_date=datetime.strptime(transaction['payment_date'], '%Y-%m-%d'),
                reference_number=transaction['reference_number'],
                account_number=transaction['account_number'],
                amount=float(transaction['amount']),
                created_by=1,  # Dummy user ID for test
                updated_by=1   # Dummy user ID for test
            )
            
            db.add(new_transaction)
            processed_transactions.append(new_transaction)
        
        # Commit all transactions
        db.commit()
        
        # Format the response
        response = {
            'batch_id': str(batch.id),
            'batch_reference': batch.batch_reference,
            'account_id': str(account_id),
            'start_date': batch.start_date.strftime('%Y-%m-%d'),
            'end_date': batch.end_date.strftime('%Y-%m-%d'),
            'total_amount': float(batch.total_batch_amount),
            'transactions_processed': len(processed_transactions),
            'transactions': [
                {
                    'id': str(t.id),
                    'transaction_id': t.transaction_id,
                    'payment_date': t.payment_date.strftime('%Y-%m-%d'),
                    'reference_number': t.reference_number,
                    'amount': float(t.amount)
                }
                for t in processed_transactions
            ]
        }
        
        return {
            'status': 'success',
            'data': response
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 