from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from database.db_connector import DBConnector
from applications.models.models import BankTransaction, BankReconciliation, Payment
from datetime import datetime

bank_reconciliation_bp = Blueprint('bank_reconciliation', __name__)

@bank_reconciliation_bp.route('/api/bank-reconciliation', methods=['POST'])
@jwt_required()
def reconcile_payments():
    """
    Endpoint to reconcile bank transactions with payments.
    Matches transactions based on reference number and payment date.
    """
    try:
        db = DBConnector().get_session()
        
        # Get all unreconciled bank transactions
        unmatched_transactions = db.query(BankTransaction).filter(
            BankTransaction.is_reconciled == False,
            BankTransaction.is_active == True
        ).all()
        
        reconciled_count = 0
        for transaction in unmatched_transactions:
            # Look for matching payment by reference and date
            matching_payment = db.query(Payment).filter(
                Payment.bank_reference == transaction.reference_number,
                Payment.payment_date == transaction.payment_date,
                Payment.deleted_at.is_(None),
                Payment.is_active == True
            ).first()
            
            if matching_payment:
                # Create reconciliation record
                reconciliation = BankReconciliation(
                    bank_transaction_id=transaction.id,
                    payment_id=matching_payment.id,
                    status='matched',
                    created_at=datetime.utcnow()
                )
                db.add(reconciliation)
                
                # Mark transaction as reconciled
                transaction.is_reconciled = True
                transaction.updated_at = datetime.utcnow()
                
                reconciled_count += 1
        
        # Commit all changes
        db.commit()
        
        return jsonify({
            "message": "Reconciliation process completed",
            "transactions_processed": len(unmatched_transactions),
            "matches_found": reconciled_count
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({
            "message": "Error during reconciliation process",
            "error": str(e)
        }), 500
    finally:
        db.close() 