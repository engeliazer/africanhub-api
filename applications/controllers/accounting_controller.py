import traceback
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import and_, func, cast, Date

from applications.models.models import (
    Payment, PaymentDetail, Application, PaymentStatus, 
    ApplicationDetail, Subject, BankDetails, BankTransaction, BankStatementBatch, BankReconciliation, PaymentApproval,
    ApplicationStatus, ReconciliationStatus, PaymentMethodModel
)
from auth.models.models import User, UserRole, Role
from database.db_connector import db_session, DBConnector
from public.controllers.sms_controller import SMSService

accounting_bp = Blueprint('accounting_controller', __name__)

class AccountingController:
    def __init__(self, db: DBConnector):
        self.db = db

    def reconcile_payments(self) -> Dict[str, Any]:
        """Reconcile bank transactions with payments"""
        try:
            print("Starting bank reconciliation process")
            # Get all unreconciled bank transactions
            unmatched_transactions = self.db.query(BankTransaction).filter(
                and_(
                    BankTransaction.is_reconciled == False,
                    BankTransaction.is_active == True
                )
            ).all()
            
            print(f"Found {len(unmatched_transactions)} unmatched transactions")
            reconciled_count = 0
            for transaction in unmatched_transactions:
                try:
                    print(f"\nProcessing transaction {transaction.id}:")
                    print(f"Reference number: {transaction.reference_number}")
                    print(f"Payment date: {transaction.payment_date}")
                    print(f"Amount: {transaction.amount}")
                    
                    # Look for matching payment by reference and amount only
                    matching_payment = self.db.query(Payment).filter(
                        and_(
                            Payment.bank_reference == transaction.reference_number,
                            Payment.amount == transaction.amount,
                            Payment.deleted_at.is_(None),
                            Payment.is_active == True
                        )
                    ).first()
                    
                    if matching_payment:
                        print(f"Found matching payment {matching_payment.id}:")
                        print(f"Bank reference: {matching_payment.bank_reference}")
                        print(f"Payment date: {matching_payment.payment_date}")
                        print(f"Amount: {matching_payment.amount}")
                        
                        # Create reconciliation record
                        reconciliation = BankReconciliation(
                            bank_transaction_id=transaction.id,
                            payment_id=matching_payment.id,
                            status='matched',
                            created_at=datetime.utcnow()
                        )
                        self.db.add(reconciliation)
                        
                        # Mark transaction as reconciled
                        transaction.is_reconciled = True
                        transaction.updated_at = datetime.utcnow()
                        
                        reconciled_count += 1
                    else:
                        print("No matching payment found")
                        # Log the SQL query for debugging
                        query = self.db.query(Payment).filter(
                            and_(
                                Payment.bank_reference == transaction.reference_number,
                                Payment.amount == transaction.amount,
                                Payment.deleted_at.is_(None),
                                Payment.is_active == True
                            )
                        )
                        print("SQL Query:", str(query))
                        
                except Exception as transaction_error:
                    print(f"Error processing transaction {transaction.id}: {str(transaction_error)}")
                    # Continue with other transactions even if one fails
            
            # Commit all changes
            try:
                self.db.commit()
                print(f"Successfully committed {reconciled_count} reconciliations")
            except Exception as commit_error:
                print(f"Error committing reconciliations: {str(commit_error)}")
                self.db.rollback()
                raise commit_error
            
            return {
                "transactions_processed": len(unmatched_transactions),
                "matches_found": reconciled_count
            }
            
        except Exception as e:
            print(f"Error in reconcile_payments: {str(e)}")
            traceback.print_exc()
            self.db.rollback()
            raise e

    def get_pending_payments(self, role: str = None) -> List[Dict[str, Any]]:
        """Get all pending payments with detailed information filtered by role"""
        try:
            # First, run the bank reconciliation process
            try:
                reconciliation_result = self.reconcile_payments()
                print(f"Reconciliation result: {reconciliation_result}")
            except Exception as reconciliation_error:
                print(f"Error during reconciliation: {str(reconciliation_error)}")
                # Continue with getting pending payments even if reconciliation fails
            
            # Base query for payments with all necessary joins
            payments_query = self.db.query(Payment).distinct().outerjoin(
                PaymentDetail, Payment.id == PaymentDetail.payment_id
            ).outerjoin(
                Application, PaymentDetail.application_id == Application.id
            ).outerjoin(
                BankReconciliation, Payment.id == BankReconciliation.payment_id
            ).filter(
                and_(
                    Payment.deleted_at.is_(None),
                    Payment.is_active == True
                )
            )

            # Add role-based filtering
            if role:
                if role.upper() == 'MANAGER':
                    payments_query = payments_query.filter(BankReconciliation.status == 'verified')
                elif role.upper() == 'ACCOUNTANT':
                    payments_query = payments_query.filter(BankReconciliation.status == 'matched')
                else:
                    raise BadRequest(f"Invalid role: {role}. Must be either 'MANAGER' or 'ACCOUNTANT'")
            
            # Execute query and get results
            payments = payments_query.all()
            print(f"Found {len(payments)} payments")
            
            result = []
            for payment in payments:
                print(f"\nProcessing payment {payment.id}")
                payment_data = {
                    'id': payment.id,
                    'transaction_id': payment.transaction_id,
                    'amount': payment.amount,
                    'payment_method': payment.payment_method,
                    'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                    'bank_reference': payment.bank_reference,
                    'mobile_number': payment.mobile_number,
                    'description': payment.description,
                    'payment_details': []
                }
                
                # Get payment details directly
                payment_details = self.db.query(PaymentDetail).filter(
                    PaymentDetail.payment_id == payment.id,
                    PaymentDetail.is_active == True,
                    PaymentDetail.deleted_at.is_(None)
                ).all()
                
                print(f"Payment has {len(payment_details)} payment details")
                
                for detail in payment_details:
                    # Get application with user information in a single query
                    application_with_user = self.db.query(
                        Application, User
                    ).join(
                        User, Application.user_id == User.id
                    ).filter(
                        Application.id == detail.application_id,
                        Application.is_active == True,
                        Application.deleted_at.is_(None)
                    ).first()
                    
                    if application_with_user:
                        application, user = application_with_user
                        try:
                            print(f"Processing application {application.id}")
                            
                            # Get reconciliation status
                            reconciliation = self.db.query(BankReconciliation).filter(
                                BankReconciliation.payment_id == payment.id
                            ).first()
                            
                            detail_data = {
                                'id': detail.id,
                                'application_id': application.id,
                                'amount': detail.amount,
                                'application_status': application.status.value,
                                'payment_status': application.payment_status.value,
                                'reconciliation_status': reconciliation.status if reconciliation else None,
                    'student': {
                        'id': user.id,
                                    'name': f"{user.first_name} {user.last_name}",
                                    'email': user.email
                                } if user else None
                            }
                            payment_data['payment_details'].append(detail_data)
                            print(f"Successfully added payment detail for application {application.id}")
                        except Exception as detail_error:
                            print(f"Error processing payment detail: {str(detail_error)}")
                            traceback.print_exc()
                            # Continue with other details even if one fails
                    else:
                        print(f"No application or user found for payment detail {detail.id}")
                
                result.append(payment_data)
            
            return result
        except Exception as e:
            print(f"Error in get_pending_payments: {str(e)}")
            traceback.print_exc()
            raise BadRequest(f"Error retrieving pending payments: {str(e)}")

    def get_payment_details(self, payment_id: int) -> Dict[str, Any]:
        """Get detailed information for a specific payment"""
        try:
            print(f"Getting payment details for payment_id: {payment_id}")
            
            # Get the payment with all related information
            payment = self.db.query(Payment).filter(
                Payment.id == payment_id,
                Payment.is_active == True
            ).first()
            
            if not payment:
                print("Payment not found")
                raise NotFound("Payment not found")
            
            print(f"Found payment: {payment}")
            
            # Get the payment details
            payment_details = self.db.query(PaymentDetail).filter(
                PaymentDetail.payment_id == payment_id,
                PaymentDetail.is_active == True
            ).first()
            
            if not payment_details:
                print("Payment details not found")
                raise NotFound("Payment details not found")
            
            # Get the application
            application = self.db.query(Application).filter(
                Application.id == payment_details.application_id,
                Application.is_active == True
            ).first()
            
            if not application:
                print(f"Application not found for payment detail {payment_details.id}")
                raise NotFound("Application not found")
            
            # Get application details
            application_details = self.db.query(ApplicationDetail).filter(
                ApplicationDetail.application_id == application.id,
                ApplicationDetail.is_active == True
            ).all()
            
            # Get subjects information
            subjects = []
            for app_detail in application_details:
                subject = app_detail.subject
                subjects.append({
                    'id': subject.id,
                    'name': subject.name,
                    'code': subject.code
                })
            
            # Get student information
            student = self.db.query(User).filter(User.id == application.user_id).first()
            
            # Get reconciliation status with joined data from BankTransaction and Payment
            reconciliation = self.db.query(BankReconciliation).join(
                BankTransaction, BankReconciliation.bank_transaction_id == BankTransaction.id
            ).join(
                Payment, BankReconciliation.payment_id == Payment.id
            ).filter(
                BankReconciliation.payment_id == payment.id
            ).first()
            
            # Format the response according to the agreed structure
            reconciliation_data = None
            if reconciliation and reconciliation.bank_transaction:
                reconciliation_data = {
                    'id': reconciliation.id,
                    'payment_id': reconciliation.payment_id,
                    'bank_transaction_id': reconciliation.bank_transaction_id,
                    'reconciliation_date': reconciliation.created_at.isoformat() if reconciliation.created_at else None,
                    'status': reconciliation.status,
                    'payer_reference': payment.bank_reference,
                    'bank_reference': reconciliation.bank_transaction.reference_number if reconciliation.bank_transaction else None,
                    'bank_transaction': {
                        'id': reconciliation.bank_transaction.id,
                        'reference_number': reconciliation.bank_transaction.reference_number,
                        'payment_date': reconciliation.bank_transaction.payment_date.isoformat() if reconciliation.bank_transaction.payment_date else None,
                        'amount': reconciliation.bank_transaction.amount,
                        'is_reconciled': reconciliation.bank_transaction.is_reconciled
                    } if reconciliation.bank_transaction else None
                }
            else:
                # If no reconciliation exists, create a default structure
                reconciliation_data = {
                    'id': None,
                    'payment_id': payment.id,
                    'bank_transaction_id': None,
                    'reconciliation_date': None,
                    'status': 'pending',
                    'payer_reference': payment.bank_reference,
                    'bank_reference': None,
                    'bank_transaction': None
                }
            
            payment_data = {
                'id': payment.id,
                'transaction_id': payment.transaction_id,
                'amount': payment.amount,
                'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                'payment_method': payment.payment_method,
                'status': payment.payment_status.value,
                'student': {
                    'id': student.id,
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'email': student.email
                } if student else None,
                'application': {
                    'id': application.id,
                    'subjects': subjects
                },
                'reconciliation': reconciliation_data
            }
            
            print("Successfully processed payment details")
            return payment_data
            
        except Exception as e:
            print(f"Error in get_payment_details: {str(e)}")
            traceback.print_exc()
            raise BadRequest(f"Error retrieving payment details: {str(e)}")

    def get_default_bank_details(self) -> Dict[str, Any]:
        """Get the default bank details for collection"""
        try:
            # Get the default bank details
            bank_details = (
                self.db.query(BankDetails)
                .filter(BankDetails.is_default == True)
                .filter(BankDetails.is_active == True)
                .first()
            )
            
            if not bank_details:
                raise NotFound('No default bank details found')
            
            # Format the response
            response = {
                'id': str(bank_details.id),
                'bank_name': bank_details.bank_name,
                'account_name': bank_details.account_name,
                'account_number': bank_details.account_number,
                'branch_code': bank_details.branch_code,
                'swift_code': bank_details.swift_code
            }
            
            return response
            
        except Exception as e:
            raise e

    def list_bank_details(self) -> List[Dict[str, Any]]:
        """List all active bank details"""
        try:
            rows = (
                self.db.query(BankDetails)
                .filter(BankDetails.is_active == True)
                .order_by(BankDetails.is_default.desc(), BankDetails.bank_name)
                .all()
            )
            return [self._bank_details_to_dict(b) for b in rows]
        except Exception as e:
            raise e

    def get_bank_details_by_id(self, bank_details_id: int) -> Dict[str, Any]:
        """Get a single bank details record by ID"""
        try:
            bank = (
                self.db.query(BankDetails)
                .filter(BankDetails.id == bank_details_id, BankDetails.is_active == True)
                .first()
            )
            if not bank:
                raise NotFound('Bank details not found')
            return self._bank_details_to_dict(bank)
        except NotFound:
            raise
        except Exception as e:
            raise e

    def _bank_details_to_dict(self, b: BankDetails) -> Dict[str, Any]:
        """Convert BankDetails model to API response dict"""
        return {
            'id': b.id,
            'bank_name': b.bank_name,
            'account_name': b.account_name,
            'account_number': b.account_number,
            'branch_code': b.branch_code,
            'swift_code': b.swift_code,
            'is_default': b.is_default,
            'is_active': b.is_active,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'updated_at': b.updated_at.isoformat() if b.updated_at else None,
            'created_by': b.created_by,
            'updated_by': b.updated_by,
        }

    def create_bank_details(self, data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Create a new bank details record"""
        try:
            bank_name = data.get('bank_name')
            account_name = data.get('account_name')
            account_number = data.get('account_number')
            branch_code = data.get('branch_code')
            swift_code = data.get('swift_code')
            is_default = data.get('is_default', False)

            if not all([bank_name, account_name, account_number, branch_code]):
                raise BadRequest('bank_name, account_name, account_number, and branch_code are required')

            # Ensure only one is_default: clear all others when this one will be default
            if is_default:
                self.db.query(BankDetails).update(
                    {BankDetails.is_default: False},
                    synchronize_session=False
                )

            bank = BankDetails(
                bank_name=bank_name,
                account_name=account_name,
                account_number=account_number,
                branch_code=branch_code,
                swift_code=swift_code or None,
                is_default=bool(is_default),
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
            self.db.add(bank)
            self.db.commit()
            self.db.refresh(bank)
            return self._bank_details_to_dict(bank)
        except IntegrityError as e:
            self.db.rollback()
            raise BadRequest(f'Invalid bank details or duplicate: {str(e)}')
        except BadRequest:
            raise
        except Exception as e:
            self.db.rollback()
            raise e

    def update_bank_details(self, bank_details_id: int, data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Update an existing bank details record"""
        try:
            bank = (
                self.db.query(BankDetails)
                .filter(BankDetails.id == bank_details_id, BankDetails.is_active == True)
                .first()
            )
            if not bank:
                raise NotFound('Bank details not found')

            # Ensure only one is_default: clear all others when this one is set to default
            is_default = data.get('is_default')
            if is_default is True:
                self.db.query(BankDetails).filter(BankDetails.id != bank_details_id).update(
                    {BankDetails.is_default: False},
                    synchronize_session=False
                )

            for key in ('bank_name', 'account_name', 'account_number', 'branch_code', 'swift_code', 'is_default', 'is_active'):
                if key in data:
                    setattr(bank, key, data[key] if key != 'swift_code' else (data[key] or None))
            bank.updated_by = user_id
            bank.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(bank)
            return self._bank_details_to_dict(bank)
        except NotFound:
            raise
        except IntegrityError as e:
            self.db.rollback()
            raise BadRequest(f'Invalid bank details or duplicate: {str(e)}')
        except Exception as e:
            self.db.rollback()
            raise e

    def delete_bank_details(self, bank_details_id: int, user_id: int) -> Dict[str, Any]:
        """Soft-delete a bank details record (set is_active=False)"""
        try:
            bank = (
                self.db.query(BankDetails)
                .filter(BankDetails.id == bank_details_id, BankDetails.is_active == True)
                .first()
            )
            if not bank:
                raise NotFound('Bank details not found')

            bank.is_active = False
            bank.updated_by = user_id
            bank.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(bank)
            return {'id': bank.id, 'message': 'Bank details deactivated successfully'}
        except NotFound:
            raise
        except Exception as e:
            self.db.rollback()
            raise e

    def upload_bank_statement(self, data: Dict[str, Any], current_user_id: int) -> Dict[str, Any]:
        """Upload bank statement transactions"""
        try:
            # Get the account_id from the request
            account_id = data.get('account_id')
            if not account_id:
                raise BadRequest('Account ID is required')
            
            # Verify that the bank account exists
            bank_account = (
                self.db.query(BankDetails)
                .filter(BankDetails.id == int(account_id))
                .filter(BankDetails.is_active == True)
                .first()
            )
            
            if not bank_account:
                raise NotFound('Bank account not found')
            
            # Get the transactions from the request
            transactions = data.get('transactions', [])
            if not transactions:
                raise BadRequest('No transactions provided')
            
            # Calculate batch totals
            total_amount = sum(float(t['amount']) for t in transactions)
            start_date = min(datetime.strptime(t['payment_date'], '%Y-%m-%d') for t in transactions)
            end_date = max(datetime.strptime(t['payment_date'], '%Y-%m-%d') for t in transactions)
            
            # Create a new batch
            batch = BankStatementBatch(
                account_id=int(account_id),
                batch_reference=f"BATCH_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                start_date=start_date,
                end_date=end_date,
                number_of_transactions=len(transactions),
                total_batch_amount=total_amount,
                created_by=current_user_id,
                updated_by=current_user_id
            )
            
            self.db.add(batch)
            self.db.flush()  # Get the batch ID without committing
            
            # Process each transaction
            processed_transactions = []
            for transaction in transactions:
                # Check if transaction already exists
                existing_transaction = (
                    self.db.query(BankTransaction)
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
                    created_by=current_user_id,
                    updated_by=current_user_id
                )
                
                self.db.add(new_transaction)
                processed_transactions.append(new_transaction)
            
            # Commit all transactions
            self.db.commit()
            
            # Format the response
            response = {
                'batch_id': str(batch.id),
                'batch_reference': batch.batch_reference,
                'account_id': str(account_id),
                'bank_name': bank_account.bank_name,
                'account_number': bank_account.account_number,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_amount': float(total_amount),
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
            
            return response
            
        except Exception as e:
            self.db.rollback()
            raise e

    def review_payment(self, reconciliation_id: int, status: str, user_id: int) -> Dict[str, Any]:
        """Review a payment reconciliation (verify, approve, or reject)"""
        try:
            # Validate status
            if status not in ['verified', 'approved', 'rejected']:
                return {
                    'status': 'error',
                    'message': 'Invalid status. Must be verified, approved, or rejected'
                }

            # Get the reconciliation record
            reconciliation = self.db.query(BankReconciliation).filter(
                BankReconciliation.id == reconciliation_id,
                BankReconciliation.is_active == True
            ).first()
            
            if not reconciliation:
                return {
                    'status': 'error',
                    'message': 'Reconciliation record not found'
                }

            # Get the associated payment
            payment = self.db.query(Payment).filter(
                Payment.id == reconciliation.payment_id,
                Payment.is_active == True
            ).first()
        
            if not payment:
                return {
                    'status': 'error',
                    'message': 'Associated payment not found'
                }

            # Get all applications associated with this payment through payment details
            applications = self.db.query(Application).join(
                PaymentDetail, Application.id == PaymentDetail.application_id
            ).filter(
                PaymentDetail.payment_id == payment.id,
                Application.is_active == True
            ).all()

            if not applications:
                return {
                    'status': 'error',
                    'message': 'No applications found for this payment'
                }

            # Store the previous status
            previous_status = reconciliation.status

            # Update the reconciliation status
            reconciliation.status = status
            reconciliation.updated_at = datetime.utcnow()
            reconciliation.updated_by = user_id

            # Update application status based on reconciliation status
            for application in applications:
                if status == 'approved':
                    application.status = ApplicationStatus.approved
                    # Get the applicant's information with a join to User
                    applicant = self.db.query(User).filter(User.id == application.user_id).first()
                    if applicant and applicant.phone:
                        # Format phone number to ensure it starts with 255 followed by the last 9 digits
                        phone = applicant.phone
                        # Remove any non-digit characters
                        digits = ''.join(filter(str.isdigit, phone))
                        
                        # If the number starts with 255, return as is
                        if digits.startswith('255'):
                            formatted_phone = digits
                        else:
                            # If the number starts with 0, remove it
                            if digits.startswith('0'):
                                digits = digits[1:]
                            
                            # Ensure we have exactly 9 digits after 255
                            if len(digits) > 9:
                                digits = digits[-9:]  # Take last 9 digits
                            
                            # Add 255 prefix
                            formatted_phone = f"255{digits}"
                        
                        # Create a welcoming message
                        message = f"Welcome to The African Hub. Your application payment has been approved. You can now access all the study materials. Happy learning."

                        # Send SMS notification
                        print(f"Sending SMS to {formatted_phone} with message: {message}")
                        sms_result = SMSService.send_message(
                            phone=formatted_phone,
                            message=message,
                            process_name='payment_approved',
                            created_by=user_id,
                        )
                        print(f"SMS sending result: {sms_result}")
                elif status == 'rejected':
                    application.status = ApplicationStatus.rejected
                elif status == 'verified':
                    application.status = ApplicationStatus.verified
                application.updated_at = datetime.utcnow()
                application.updated_by = user_id

            # Create approval record
            approval = PaymentApproval(
                reconciliation_id=reconciliation.id,
                user_id=user_id,
                previous_status=previous_status,
                new_status=status,
                created_at=datetime.utcnow()
            )
            self.db.add(approval)

            # Commit changes
            self.db.commit()

            return {
            'status': 'success',
                'message': f'Payment reconciliation {status} successfully',
                'data': {
                    'reconciliation_id': reconciliation.id,
                    'payment_id': payment.id,
                    'previous_status': previous_status,
                    'new_status': status,
                    'updated_at': reconciliation.updated_at.isoformat() if reconciliation.updated_at else None,
                    'updated_by': user_id
                }
            }

        except Exception as e:
            print(f"Error in review_payment: {str(e)}")
            traceback.print_exc()
            return {
                'status': 'error',
                'message': f'Error reviewing payment: {str(e)}'
            }

    def get_reconciliation_summary(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get reconciliation summary for a specific date range"""
        try:
            # Base date filter for all queries
            date_filter = and_(
                Payment.created_at >= start_date,
                Payment.created_at <= end_date,
                Payment.deleted_at.is_(None),
            Payment.is_active == True
            )

            # 1. Payment Status Summary
            payment_status_summary = {
                "id": "payment_status",
                "title": "Payment Status Overview",
                "paid": {
                    "id": "payment_status_paid",
                    "title": "Successfully Paid Applications",
                    "count": 0,
                    "total_amount": 0
                },
                "pending": {
                    "id": "payment_status_pending",
                    "title": "Applications Awaiting Payment",
                    "count": 0,
                    "total_amount": 0
                },
                "failed": {
                    "id": "payment_status_failed",
                    "title": "Failed Payments",
                    "count": 0,
                    "total_amount": 0
                }
            }

            # Get paid applications count and amount
            paid_stats = self.db.query(
                func.count(Payment.id).label('count'),
                func.sum(Payment.amount).label('total_amount')
            ).filter(
                date_filter,
                Payment.payment_status == PaymentStatus.paid
        ).first()
        
            payment_status_summary["paid"]["count"] = paid_stats.count or 0
            payment_status_summary["paid"]["total_amount"] = float(paid_stats.total_amount or 0)

            # Get pending applications (applications with no payments)
            pending_apps = self.db.query(Application).filter(
                Application.created_at >= start_date,
                Application.created_at <= end_date,
                Application.deleted_at.is_(None),
                Application.is_active == True,
                ~Application.id.in_(
                    self.db.query(PaymentDetail.application_id).filter(
                        PaymentDetail.deleted_at.is_(None)
                    )
                )
        ).all()
        
            payment_status_summary["pending"]["count"] = len(pending_apps)
            payment_status_summary["pending"]["total_amount"] = sum(app.total_fee or 0 for app in pending_apps)

            # Get failed payments count and amount
            failed_stats = self.db.query(
                func.count(Payment.id).label('count'),
                func.sum(Payment.amount).label('total_amount')
            ).filter(
                date_filter,
                Payment.payment_status == PaymentStatus.failed
            ).first()
            
            payment_status_summary["failed"]["count"] = failed_stats.count or 0
            payment_status_summary["failed"]["total_amount"] = float(failed_stats.total_amount or 0)

            # 2. Reconciliation Summary
            reconciliation_summary = {
                "id": "reconciliation_status",
                "title": "Bank Reconciliation Status",
                "matched_records": {
                    "id": "reconciliation_matched",
                    "title": "Matched Payment Records",
                    "matched_not_verified": {
                        "id": "reconciliation_matched_not_verified",
                        "title": "Matched but Not Verified by Accountant",
                        "count": 0,
                        "total_amount": 0
                    },
                    "matched_verified": {
                        "id": "reconciliation_matched_verified",
                        "title": "Verified by Accountant",
                        "count": 0,
                        "total_amount": 0
                    },
                    "matched_approved": {
                        "id": "reconciliation_matched_approved",
                        "title": "Approved by Manager",
                        "count": 0,
                        "total_amount": 0
                    },
                    "matched_rejected": {
                        "id": "reconciliation_matched_rejected",
                        "title": "Rejected Matches",
                        "count": 0,
                        "total_amount": 0
                    }
                },
                "unmatched_records": {
                    "id": "reconciliation_unmatched",
                    "title": "Unmatched Records",
                    "paid_no_bank_transaction": {
                        "id": "reconciliation_unmatched_paid_no_bank",
                        "title": "Payments Without Bank Transactions",
                        "count": 0,
                        "total_amount": 0
                    },
                    "bank_transaction_no_payment": {
                        "id": "reconciliation_unmatched_bank_no_payment",
                        "title": "Bank Transactions Without Payments",
                        "count": 0,
                        "total_amount": 0
                    }
                }
            }

            # Get matched records statistics
            for status in ['matched', 'verified', 'approved', 'rejected']:
                matched_stats = self.db.query(
                    func.count(BankReconciliation.id).label('count'),
                    func.sum(Payment.amount).label('total_amount')
                ).join(
                    Payment, BankReconciliation.payment_id == Payment.id
                ).filter(
                    date_filter,
                    BankReconciliation.status == status,
                    BankReconciliation.is_active == True
                ).first()
                
                # Map the status to the correct key in the response
                if status == 'matched':
                    key = "matched_not_verified"
                else:
                    key = f"matched_{status}"
                
                reconciliation_summary["matched_records"][key]["count"] = matched_stats.count or 0
                reconciliation_summary["matched_records"][key]["total_amount"] = float(matched_stats.total_amount or 0)

            # Get unmatched records statistics
            # Payments without bank transactions
            paid_no_bank = self.db.query(
                func.count(Payment.id).label('count'),
                func.sum(Payment.amount).label('total_amount')
            ).filter(
                date_filter,
                Payment.payment_status == PaymentStatus.paid,
                ~Payment.id.in_(
                    self.db.query(BankReconciliation.payment_id).filter(
                        BankReconciliation.is_active == True
                    )
                )
            ).first()
            
            reconciliation_summary["unmatched_records"]["paid_no_bank_transaction"]["count"] = paid_no_bank.count or 0
            reconciliation_summary["unmatched_records"]["paid_no_bank_transaction"]["total_amount"] = float(paid_no_bank.total_amount or 0)

            # Bank transactions without payments
            bank_no_payment = self.db.query(
                func.count(BankTransaction.id).label('count'),
                func.sum(BankTransaction.amount).label('total_amount')
            ).filter(
                BankTransaction.payment_date >= start_date,
                BankTransaction.payment_date <= end_date,
                BankTransaction.is_active == True,
                ~BankTransaction.id.in_(
                    self.db.query(BankReconciliation.bank_transaction_id).filter(
                        BankReconciliation.is_active == True
                    )
                )
            ).first()
            
            reconciliation_summary["unmatched_records"]["bank_transaction_no_payment"]["count"] = bank_no_payment.count or 0
            reconciliation_summary["unmatched_records"]["bank_transaction_no_payment"]["total_amount"] = float(bank_no_payment.total_amount or 0)

            # 3. Special Cases
            special_cases = {
                "id": "special_cases",
                "title": "Special Cases Requiring Attention",
                "multiple_matches": {
                    "id": "special_cases_multiple_matches",
                    "title": "Multiple Bank Transactions Matching One Payment",
                    "count": 0,
                    "total_amount": 0
                },
                "expired_matches": {
                    "id": "special_cases_expired_matches",
                    "title": "Matches Pending Verification for Too Long",
                    "count": 0,
                    "total_amount": 0
                }
            }

            # Get multiple matches (payments with multiple bank transactions)
            multiple_matches = self.db.query(
                Payment.id,
                func.count(BankReconciliation.id).label('match_count')
            ).join(
                BankReconciliation, Payment.id == BankReconciliation.payment_id
            ).filter(
                date_filter,
                BankReconciliation.is_active == True
            ).group_by(
                Payment.id
            ).having(
                func.count(BankReconciliation.id) > 1
            ).all()
            
            special_cases["multiple_matches"]["count"] = len(multiple_matches)
            special_cases["multiple_matches"]["total_amount"] = sum(
                payment.amount for payment in self.db.query(Payment).filter(
                    Payment.id.in_([m[0] for m in multiple_matches])
                ).all()
            )

            # Get expired matches (matches pending verification for more than 7 days)
            expired_date = datetime.utcnow() - timedelta(days=7)
            expired_matches = self.db.query(
                func.count(BankReconciliation.id).label('count'),
                func.sum(Payment.amount).label('total_amount')
            ).join(
                Payment, BankReconciliation.payment_id == Payment.id
            ).filter(
                date_filter,
                BankReconciliation.status == 'matched',
                BankReconciliation.created_at <= expired_date,
                BankReconciliation.is_active == True
            ).first()
            
            special_cases["expired_matches"]["count"] = expired_matches.count or 0
            special_cases["expired_matches"]["total_amount"] = float(expired_matches.total_amount or 0)

            return {
                "payment_status_summary": payment_status_summary,
                "reconciliation_summary": reconciliation_summary,
                "special_cases": special_cases
            }

        except Exception as e:
            print(f"Error in get_reconciliation_summary: {str(e)}")
            traceback.print_exc()
            raise BadRequest(f"Error retrieving reconciliation summary: {str(e)}")

    def get_reconciliation_summary_details(self, category: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed information for a specific reconciliation summary category"""
        try:
            # Special handling for pending payments (applications with no payment records)
            if category == "payment_status_pending":
                # Get applications with no payment records
                query = (
                    self.db.query(Application)
                    .outerjoin(PaymentDetail)
                    .outerjoin(User, Application.user_id == User.id)
                    .options(
                        joinedload(Application.user),
                        joinedload(Application.details).joinedload(ApplicationDetail.subject)
                    )
                    .filter(
                        and_(
                            Application.created_at.between(start_date, end_date),
                            Application.is_active == True,
                            PaymentDetail.id.is_(None)  # No payment records
                        )
                    )
                )
                
                applications = query.all()
                
                # Format the response
                formatted_results = []
                for application in applications:
                    # Get the first application detail (assuming one application can have multiple subjects)
                    application_detail = application.details[0] if application.details else None
                    
                    # Get subject information
                    subject = application_detail.subject if application_detail else None
                    
                    formatted_result = {
                        "application": {
                            "id": application.id,
                            "total_fee": float(application.total_fee) if application.total_fee else 0.0,
                            "status": application.status.value,
                            "payment_status": application.payment_status.value,
                            "applicant": {
                                "id": application.user.id if application.user else None,
                                "name": f"{application.user.first_name} {application.user.middle_name} {application.user.last_name}".strip() if application.user else None,
                                "email": application.user.email if application.user else None,
                                "phone": application.user.phone if application.user else None
                            } if application.user else None,
                            "subject": {
                                "id": subject.id if subject else None,
                                "name": subject.name if subject else None,
                                "code": subject.code if subject else None
                            } if subject else None
                        }
                    }
                    
                    formatted_results.append(formatted_result)
                
                return {
                    "status": "success",
                    "count": len(formatted_results),
                    "records": formatted_results
                }
            
            # For all other categories, use the existing logic for payments
            # Create base payment query
            base_query = (
                self.db.query(Payment)
                .filter(Payment.created_at.between(start_date, end_date))
            )

            # Apply category-specific filters
            if category == "payment_status_paid":
                base_query = base_query.filter(Payment.payment_status == PaymentStatus.paid)
            elif category == "payment_status_failed":
                base_query = base_query.filter(Payment.payment_status == PaymentStatus.failed)
            elif category == "reconciliation_matched_verified":
                base_query = (
                    base_query.join(BankReconciliation)
                    .filter(BankReconciliation.status == ReconciliationStatus.verified)
                )
            elif category == "reconciliation_matched_not_verified":
                base_query = (
                    base_query.join(BankReconciliation)
                    .filter(BankReconciliation.status == ReconciliationStatus.matched)
                )
            elif category == "reconciliation_matched_approved":
                base_query = (
                    base_query.join(BankReconciliation)
                    .filter(BankReconciliation.status == ReconciliationStatus.approved)
                )
            elif category == "reconciliation_matched_rejected":
                base_query = (
                    base_query.join(BankReconciliation)
                    .filter(BankReconciliation.status == ReconciliationStatus.rejected)
                )
            elif category == "reconciliation_unmatched_paid_no_bank":
                base_query = base_query.filter(~Payment.reconciliations.any())
            elif category == "reconciliation_unmatched_bank_no_payment":
                base_query = (
                    self.db.query(BankTransaction)
                    .filter(
                        BankTransaction.created_at.between(start_date, end_date),
                        BankTransaction.is_active == True,
                        ~BankTransaction.reconciliations.any()
                    )
                )
            elif category == "special_cases_multiple_matches":
                base_query = (
                    base_query.join(BankReconciliation)
                    .group_by(Payment.id)
                    .having(func.count(BankReconciliation.id) > 1)
                )
            elif category == "special_cases_expired_matches":
                base_query = (
                    base_query.join(BankReconciliation)
                    .filter(
                        BankReconciliation.status == ReconciliationStatus.matched,
                        BankReconciliation.created_at <= datetime.utcnow() - timedelta(days=7)
                    )
                )

            # Get unique payment IDs first to avoid duplicates
            payment_ids = [p.id for p in base_query.with_entities(Payment.id).all()]

            # Now fetch the full details with joins
            if category == "reconciliation_unmatched_bank_no_payment":
                records = (
                    self.db.query(BankTransaction)
                    .filter(BankTransaction.id.in_(payment_ids))
                    .options(
                        joinedload(BankTransaction.bank_details),
                        joinedload(BankTransaction.bank_statement_batch)
                    )
                    .all()
                )
            else:
                records = (
                    self.db.query(Payment)
                    .filter(Payment.id.in_(payment_ids))
                    .options(
                        joinedload(Payment.payment_details).joinedload(PaymentDetail.application).joinedload(Application.details).joinedload(ApplicationDetail.subject),
                        joinedload(Payment.payment_details).joinedload(PaymentDetail.application).joinedload(Application.user),
                        joinedload(Payment.reconciliations).joinedload(BankReconciliation.bank_transaction)
                    )
                    .all()
                )

            # Format the response
            formatted_records = []
            for record in records:
                if category == "reconciliation_unmatched_bank_no_payment":
                    formatted_records.append({
                        "id": record.id,
                        "transaction_id": record.transaction_id,
                        "payment_date": record.payment_date.isoformat() if record.payment_date else None,
                        "reference_number": record.reference_number,
                        "account_number": record.account_number,
                        "amount": float(record.amount),
                        "bank_details": {
                            "bank_name": record.bank_details.bank_name if record.bank_details else None,
                            "branch_name": record.bank_details.branch_name if record.bank_details else None
                        } if record.bank_details else None,
                        "batch_reference": record.bank_statement_batch.batch_reference if record.bank_statement_batch else None
                    })
                else:
                    # Get application details from payment details
                    payment_detail = record.payment_details[0] if record.payment_details else None
                    application = payment_detail.application if payment_detail else None
                    user = application.user if application else None
                    application_detail = application.details[0] if application and application.details else None
                    
                    # Get subject information
                    subject = application_detail.subject if application_detail else None
                    
                    formatted_records.append({
                        "id": record.id,
                        "reference": record.bank_reference,
                        "amount": float(record.amount),
                        "payment_date": record.payment_date.isoformat() if record.payment_date else None,
                        "payment_status": record.payment_status.value,
                        "application": {
                            "id": application.id if application else None,
                            "total_fee": float(application.total_fee) if application and application.total_fee else 0.0,
                            "status": application.status.value if application else None,
                            "payment_status": application.payment_status.value if application else None,
                            "applicant": {
                                "id": user.id if user else None,
                                "name": f"{user.first_name} {user.middle_name} {user.last_name}".strip() if user else None,
                                "email": user.email if user else None,
                                "phone": user.phone if user else None
                            } if user else None,
                            "subject": {
                                "id": subject.id if subject else None,
                                "name": subject.name if subject else None,
                                "code": subject.code if subject else None
                            } if subject else None
                        } if application else None,
                        "bank_reconciliations": [{
                            "id": rec.id,
                            "status": rec.status.value,
                            "bank_transaction": {
                                "id": rec.bank_transaction.id,
                                "transaction_id": rec.bank_transaction.transaction_id,
                                "reference_number": rec.bank_transaction.reference_number,
                                "account_number": rec.bank_transaction.account_number,
                                "amount": float(rec.bank_transaction.amount),
                                "payment_date": rec.bank_transaction.payment_date.isoformat() if rec.bank_transaction.payment_date else None
                            } if rec.bank_transaction else None
                        } for rec in record.reconciliations] if record.reconciliations else []
                    })

            return {
                "status": "success",
                "count": len(formatted_records),
                "records": formatted_records
            }

        except Exception as e:
            print(f"Error in get_reconciliation_summary_details: {str(e)}")
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Error retrieving reconciliation summary details: {str(e)}"
            }

    def get_user_payment_history(self, user_id: int) -> Dict[str, Any]:
        """Get payment history for a specific user"""
        try:
            # Get all applications for the user
            applications = self.db.query(Application).filter(
                Application.user_id == user_id,
                Application.is_active == True
            ).all()
            
            if not applications:
                return {
                    'status': 'success',
                    'message': 'No applications found for this user',
                    'data': {
                        'applications': [],
                        'total_payments': 0,
                        'total_amount': 0.0
                    }
                }
            
            # Get all payment details for these applications
            payment_details = self.db.query(PaymentDetail).join(
                Payment, PaymentDetail.payment_id == Payment.id
            ).filter(
                PaymentDetail.application_id.in_([app.id for app in applications]),
                PaymentDetail.is_active == True,
                Payment.deleted_at.is_(None)
            ).all()
            
            # Get all payments for these payment details
            payment_ids = [detail.payment_id for detail in payment_details]
            payments = self.db.query(Payment).filter(
                Payment.id.in_(payment_ids),
                Payment.is_active == True
            ).all()
            
            # Get reconciliation status for these payments
            reconciliations = self.db.query(BankReconciliation).filter(
                BankReconciliation.payment_id.in_(payment_ids),
                BankReconciliation.is_active == True
            ).all()
            
            # Create a dictionary of reconciliation status by payment ID
            reconciliation_status = {rec.payment_id: rec.status for rec in reconciliations}
            
            # Format the response
            formatted_payments = []
            total_amount = 0.0
            
            for payment in payments:
                # Get the application details for this payment
                payment_detail = next((detail for detail in payment_details if detail.payment_id == payment.id), None)
                if not payment_detail:
                    continue
                
                application = next((app for app in applications if app.id == payment_detail.application_id), None)
                if not application:
                    continue
                
                # Get the reconciliation status
                status = reconciliation_status.get(payment.id, 'pending')
                
                # Get application details to find subjects
                application_details = self.db.query(ApplicationDetail).filter(
                    ApplicationDetail.application_id == application.id,
                    ApplicationDetail.is_active == True
                ).all()
                
                # Get subject information
                subjects = []
                for app_detail in application_details:
                    subject = self.db.query(Subject).filter(
                        Subject.id == app_detail.subject_id,
                        Subject.is_active == True
                    ).first()
                    
                    if subject:
                        subjects.append({
                            'id': subject.id,
                            'name': subject.name,
                            'code': subject.code
                        })
                
                # Format the payment data
                payment_data = {
                    'id': payment.id,
                    'transaction_id': payment.transaction_id,
                    'amount': float(payment.amount),
                    'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                    'payment_method': payment.payment_method,
                    'bank_reference': payment.bank_reference,
                    'status': status,
                    'application': {
                        'id': application.id,
                        'total_fee': float(application.total_fee) if application.total_fee else 0.0,
                        'status': application.status.value,
                        'payment_status': application.payment_status.value,
                        'subjects': subjects
                    }
                }
                
                formatted_payments.append(payment_data)
                total_amount += float(payment.amount)
            
            # Sort payments by date (newest first)
            formatted_payments.sort(key=lambda x: x['payment_date'] if x['payment_date'] else '', reverse=True)
            
            return {
                'status': 'success',
                'message': 'Payment history retrieved successfully',
                'data': {
                    'applications': formatted_payments,
                    'total_payments': len(formatted_payments),
                    'total_amount': total_amount
                }
            }
            
        except Exception as e:
            print(f"Error in get_user_payment_history: {str(e)}")
            traceback.print_exc()
            return {
                'status': 'error',
                'message': f'Error retrieving payment history: {str(e)}'
            }

    def get_payment_methods(self) -> Dict[str, Any]:
        """Get available payment methods"""
        try:
            # Fetch payment methods from the database
            payment_methods = self.db.query(PaymentMethodModel).filter(
                PaymentMethodModel.is_active == True
            ).all()
            
            # Format the response
            formatted_methods = [
                {
                    "id": method.id,
                    "name": method.name,
                    "code": method.code,
                    "icon": method.icon,
                    "is_active": method.is_active,
                    "description": method.description,
                    "instructions": method.instructions
                }
                for method in payment_methods
            ]
            
            return {
                'status': 'success',
                'payment_methods': formatted_methods
            }
            
        except Exception as e:
            print(f"Error in get_payment_methods: {str(e)}")
            traceback.print_exc()
            return {
                'status': 'error',
                'message': f'Error retrieving payment methods: {str(e)}'
            }

    def get_general_report(self, start_date: datetime, end_date: datetime, user_id: int) -> Dict[str, Any]:
        """Get a detailed accounting report for approved payments within a date range"""
        try:
            # Get user information
            user = self.db.query(User).filter(
                User.id == user_id,
                User.status == 'ACTIVE'
            ).first()
            
            if not user:
                return {
                    'status': 'error',
                    'message': 'User not found'
                }
            
            # Get user role
            user_role = self.db.query(UserRole).join(
                Role, UserRole.role_id == Role.id
            ).filter(
                UserRole.user_id == user_id,
                UserRole.is_active == True
            ).first()
            
            role_name = user_role.role.name if user_role and user_role.role else "Unknown"
            
            # Base query for approved payments within the date range
            base_query = self.db.query(Payment).filter(
                Payment.payment_status == PaymentStatus.paid,
                Payment.created_at.between(start_date, end_date),
                Payment.is_active == True,
                Payment.deleted_at.is_(None)
            )
            
            # Get all approved payments
            payments = base_query.all()
            
            # Format the detailed payment information
            formatted_payments = []
            
            for payment in payments:
                # Get payment details to find applications
                payment_details = self.db.query(PaymentDetail).filter(
                    PaymentDetail.payment_id == payment.id,
                    PaymentDetail.is_active == True
                ).all()
                
                # Get reconciliation status
                reconciliation = self.db.query(BankReconciliation).filter(
                    BankReconciliation.payment_id == payment.id,
                    BankReconciliation.is_active == True
                ).first()
                
                reconciliation_status = reconciliation.status if reconciliation else 'pending'
                
                # Get bank transaction details if reconciled
                bank_details = None
                if reconciliation and reconciliation.bank_transaction:
                    bank_details = {
                        'transaction_id': reconciliation.bank_transaction.transaction_id,
                        'account_number': reconciliation.bank_transaction.account_number,
                        'transaction_date': reconciliation.bank_transaction.payment_date.strftime('%Y-%m-%d') if reconciliation.bank_transaction.payment_date else None
                    }
                
                # Process each payment detail (application)
                for detail in payment_details:
                    # Get application
                    application = self.db.query(Application).filter(
                        Application.id == detail.application_id,
                        Application.is_active == True
                    ).first()
                    
                    if application:
                        # Get applicant details
                        applicant = self.db.query(User).filter(
                            User.id == application.user_id,
                            User.status == 'ACTIVE'
                        ).first()
                        
                        applicant_info = {
                            'id': applicant.id,
                            'name': f"{applicant.first_name} {applicant.middle_name} {applicant.last_name}".strip(),
                            'email': applicant.email,
                            'phone': applicant.phone
                        } if applicant else None
                        
                        # Get application details to find subjects
                        app_details = self.db.query(ApplicationDetail).filter(
                            ApplicationDetail.application_id == application.id,
                            ApplicationDetail.is_active == True
                        ).all()
                        
                        # Get subject information
                        subject_info = None
                        
                        for app_detail in app_details:
                            if app_detail.subject:
                                subject = app_detail.subject
                                subject_info = {
                                    'code': subject.code,
                                    'name': subject.name
                                }
                                break  # Use the first subject found
                        
                        # Format the payment data
                        payment_data = {
                            'payment_id': payment.id,
                            'payment_date': payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else None,
                            'payment_reference': payment.bank_reference,
                            'amount': float(payment.amount),
                            'payment_method': payment.payment_method,
                            'payment_status': payment.payment_status.value,
                            'reconciliation_status': reconciliation_status,
                            'applicant': applicant_info,
                            'application': {
                                'id': application.id,
                                'subject': subject_info,
                                'total_fee': float(application.total_fee) if application.total_fee else 0.0
                            },
                            'bank_details': bank_details
                        }
                        
                        formatted_payments.append(payment_data)
            
            # Sort payments by date (newest first)
            formatted_payments.sort(key=lambda x: x['payment_date'] if x['payment_date'] else '', reverse=True)
            
            # Get current timestamp
            current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            
            return {
                'status': 'success',
                'data': {
                    'report_info': {
                        'title': 'Approved Payments Report',
                        'date_range': {
                            'start': start_date.strftime('%Y-%m-%d'),
                            'end': end_date.strftime('%Y-%m-%d')
                        },
                        'generated_at': current_time,
                        'generated_by': {
                            'id': user.id,
                            'name': f"{user.first_name} {user.middle_name} {user.last_name}".strip(),
                            'role': role_name
                        }
                    },
                    'payments': formatted_payments
                }
            }
            
        except Exception as e:
            print(f"Error in get_general_report: {str(e)}")
            traceback.print_exc()
            return {
                'status': 'error',
                'message': f'Error generating general report: {str(e)}'
            }

# Initialize the controller
accounting_controller = AccountingController(db_session)

@accounting_bp.route('/pending-payments/<role>', methods=['GET'])
@jwt_required()
def get_pending_payments(role):
    """Get all pending payments filtered by role"""
    try:
        print(f"Starting get_pending_payments endpoint for role: {role}")
        payments = accounting_controller.get_pending_payments(role)
        print(f"Successfully retrieved {len(payments)} pending payments")
        return jsonify({
            'status': 'success',
            'data': payments
        }), 200
    except Exception as e:
        print(f"Error in get_pending_payments endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/pending-payments/<int:payment_id>/details', methods=['GET'])
@jwt_required()
def get_payment_details(payment_id):
    """Get detailed information for a specific payment"""
    try:
        print(f"Starting get_payment_details endpoint for payment_id: {payment_id}")
        payment_details = accounting_controller.get_payment_details(payment_id)
        print("Successfully retrieved payment details")
        return jsonify({
            'status': 'success',
            'data': payment_details
        }), 200
    except NotFound as e:
        print(f"Not found error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404
    except Exception as e:
        print(f"Error in get_payment_details endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/bank_details', methods=['GET'])
@jwt_required()
def get_default_bank_details():
    """Get the default bank details for collection"""
    try:
        bank_details = accounting_controller.get_default_bank_details()
        return jsonify({
            'status': 'success',
            'data': bank_details
        }), 200
    except NotFound as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/bank_details', methods=['POST'])
@jwt_required()
def create_bank_details():
    """Create a new bank details record"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}
        bank = accounting_controller.create_bank_details(data, current_user_id)
        return jsonify({
            'status': 'success',
            'message': 'Bank details created successfully',
            'data': bank
        }), 201
    except BadRequest as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@accounting_bp.route('/bank_details/list', methods=['GET'])
@jwt_required()
def list_bank_details():
    """List all active bank details"""
    try:
        items = accounting_controller.list_bank_details()
        return jsonify({
            'status': 'success',
            'data': items
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@accounting_bp.route('/bank_details/<int:bank_details_id>', methods=['GET'])
@jwt_required()
def get_bank_details_by_id(bank_details_id):
    """Get a single bank details record by ID"""
    try:
        bank = accounting_controller.get_bank_details_by_id(bank_details_id)
        return jsonify({
            'status': 'success',
            'data': bank
        }), 200
    except NotFound as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@accounting_bp.route('/bank_details/<int:bank_details_id>', methods=['PUT'])
@jwt_required()
def update_bank_details(bank_details_id):
    """Update an existing bank details record"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}
        bank = accounting_controller.update_bank_details(bank_details_id, data, current_user_id)
        return jsonify({
            'status': 'success',
            'message': 'Bank details updated successfully',
            'data': bank
        }), 200
    except NotFound as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except BadRequest as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@accounting_bp.route('/bank_details/<int:bank_details_id>', methods=['DELETE'])
@jwt_required()
def delete_bank_details(bank_details_id):
    """Soft-delete a bank details record (deactivate)"""
    try:
        current_user_id = get_jwt_identity()
        result = accounting_controller.delete_bank_details(bank_details_id, current_user_id)
        return jsonify({
            'status': 'success',
            'message': result.get('message', 'Bank details deactivated successfully'),
            'data': result
        }), 200
    except NotFound as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@accounting_bp.route('/upload_statement', methods=['POST'])
@jwt_required()
def upload_bank_statement():
    """Upload bank statement transactions"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Invalid request format'
            }), 400
        
        # Pass the data to the controller
        response = accounting_controller.upload_bank_statement(data, current_user_id)
        
        return jsonify({
            'status': 'success',
            'data': response
        }), 201
        
    except Exception as e:
        print("Error:", str(e))  # Debug print
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/review-payment/<int:reconciliation_id>/<status>', methods=['POST'])
@jwt_required()
def review_payment(reconciliation_id: int, status: str):
    """Review a payment reconciliation and update its status"""
    try:
        print(f"Starting review_payment endpoint for reconciliation_id: {reconciliation_id}, status: {status}")
        current_user_id = get_jwt_identity()
        result = accounting_controller.review_payment(reconciliation_id, status, current_user_id)
        print("Successfully reviewed payment")
        return jsonify({
            'status': 'success',
            'data': result
        }), 200
    except NotFound as e:
        print(f"Not found error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404
    except BadRequest as e:
        print(f"Bad request error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        print(f"Error in review_payment endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/reconciliation-summary', methods=['GET'])
@jwt_required()
def get_reconciliation_summary():
    """Get reconciliation summary for a specific date range"""
    try:
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({
                "status": "error",
                "message": "start_date and end_date are required"
            }), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Set end_date to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD"
            }), 400

        summary = accounting_controller.get_reconciliation_summary(start_date, end_date)
        
        return jsonify({
            "status": "success",
            "data": summary
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@accounting_bp.route('/reconciliation-summary-details/<summary_id>', methods=['GET'])
@jwt_required()
def get_reconciliation_summary_details(summary_id: str):
    """Get detailed information for a specific reconciliation summary category"""
    try:
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({
                "status": "error",
                "message": "start_date and end_date are required"
            }), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Set end_date to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD"
            }), 400

        details = accounting_controller.get_reconciliation_summary_details(summary_id, start_date, end_date)
        
        return jsonify({
            "status": "success",
            "data": details
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@accounting_bp.route('/payment-history/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_payment_history(user_id: int):
    """Get payment history for a specific user"""
    try:
        print(f"Starting get_user_payment_history endpoint for user_id: {user_id}")
        
        # Get the current user from the JWT token
        current_user_id = int(get_jwt_identity())  # Convert to int since JWT returns string
        print(f"Current user ID: {current_user_id}")
        
        # Get payment history
        payment_history = accounting_controller.get_user_payment_history(user_id)
        print("Successfully retrieved payment history")
        return jsonify({
            'status': 'success',
            'data': payment_history
        }), 200
    except Exception as e:
        print(f"Error in get_user_payment_history endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get available payment methods"""
    try:
        payment_methods = accounting_controller.get_payment_methods()
        return jsonify(payment_methods), 200
    except Exception as e:
        print(f"Error in get_payment_methods endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@accounting_bp.route('/reports/general', methods=['GET'])
@jwt_required()
def get_general_report():
    """Get a general accounting report for approved payments within a date range"""
    try:
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({
                "status": "error",
                "message": "start_date and end_date are required"
            }), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Set end_date to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD"
            }), 400

        # Get user ID from JWT token
        user_id = get_jwt_identity()
        
        report = accounting_controller.get_general_report(start_date, end_date, user_id)
        
        return jsonify(report), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
