from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional, Dict, Any
from datetime import datetime
import random
import string
import uuid
from flask_jwt_extended import jwt_required, get_jwt_identity
import json

from applications.models.models import (
    Payment, PaymentDetail, PaymentStatus, PaymentMethod,
    ApplicationStatus, PaymentTransaction, TransactionDetail,
    ApplicationDetail, User, Subject, Course
)
from applications.models.schemas import PaymentCreate, PaymentUpdate, PaymentInDB
from auth.models.models import User
from database.db_connector import db_session

payments_bp = Blueprint('payments_controller', __name__)

class PaymentsController:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_transaction_id(self, prefix="OCPA"):
        """Generate a unique transaction ID"""
        # Format: PREFIX-RANDOMSTRING-TIMESTAMP
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"{prefix}-{random_str}-{timestamp}"
    
    def get_application_total(self, application_ids: List[int]) -> float:
        """Calculate total amount for the given applications"""
        applications = self.db.query(Application).filter(
            Application.id.in_(application_ids),
            Application.deleted_at.is_(None)
        ).all()
        
        if len(applications) != len(application_ids):
            found_ids = [a.id for a in applications]
            missing_ids = [aid for aid in application_ids if aid not in found_ids]
            raise NotFound(f"Some applications not found: {missing_ids}")
        
        return sum(app.total_fee for app in applications)
    
    def create_payment(self, payment_data: PaymentCreate) -> Dict[str, Any]:
        """Create a new payment with details"""
        try:
            # Validate required fields
            if not payment_data.transaction_id:
                raise BadRequest("Transaction ID is required")
            if not payment_data.amount or payment_data.amount <= 0:
                raise BadRequest("Amount must be greater than 0")
            if not payment_data.payment_method:
                raise BadRequest("Payment method is required")
            if not payment_data.application_ids:
                raise BadRequest("At least one application ID is required")
            
            # Get applications
            applications = self.db.query(Application).filter(
                Application.id.in_(payment_data.application_ids),
                Application.deleted_at.is_(None)
            ).all()
            
            if len(applications) != len(payment_data.application_ids):
                raise BadRequest("One or more applications not found")
            
            # Calculate total amount from applications
            total_amount = sum(app.total_fee for app in applications)
            
            # Validate total amount matches payment amount
            if abs(total_amount - payment_data.amount) > 0.01:  # Allow small floating point differences
                raise BadRequest(f"Payment amount {payment_data.amount} does not match total application fees {total_amount}")
            
            # Generate transaction ID if not provided
            transaction_id = payment_data.transaction_id
            if not transaction_id:
                transaction_id = ''.join(['OCPA-', 
                                        ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)), 
                                        '-', datetime.now().strftime("%Y%m%d%H%M%S")])
            
            # Get payment method string
            payment_method_str = payment_data.payment_method
            
            # Find the matching enum value
            payment_method_enum = None
            for method in PaymentMethod:
                if method.value == payment_method_str:
                    payment_method_enum = method
                    break
                
            if not payment_method_enum:
                raise BadRequest(f"Invalid payment method. Valid options are: {[m.value for m in PaymentMethod]}")
            
            # Create the payment record - always set payment_status to paid
            payment = Payment(
                amount=payment_data.amount,
                payment_method=payment_method_enum.value,
                transaction_id=transaction_id,
                payment_status=PaymentStatus.paid,  # Always set to paid for the payment record
                payment_date=datetime.utcnow(),
                mobile_number=payment_data.mobile_number,
                description=payment_data.description or f"Payment for applications {payment_data.application_ids}",
                is_active=True,
                created_by=payment_data.created_by,
                updated_by=payment_data.updated_by
            )
            
            self.db.add(payment)
            self.db.flush()  # This assigns an ID to payment
            
            # Determine if this is an MNO payment
            is_mno_payment = payment_method_enum in [PaymentMethod.mpesa, PaymentMethod.mixx, PaymentMethod.airtel]
            
            # Create payment details for each application
            for app in applications:
                payment_detail = PaymentDetail(
                    payment_id=payment.id,
                    application_id=app.id,
                    amount=app.total_fee,
                    is_active=True,
                    created_by=payment_data.created_by,
                    updated_by=payment_data.updated_by
                )
                self.db.add(payment_detail)
                
                # Update application payment status to paid
                app.payment_status = PaymentStatus.paid
                
                # Update application status based on payment method
                if is_mno_payment:
                    # For MNO payments, set status to approved
                    app.status = ApplicationStatus.approved
                else:
                    # For non-MNO payments, set status to pending
                    app.status = ApplicationStatus.pending
                
                app.updated_by = payment_data.updated_by
                app.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            # Prepare response
            result = {
                'id': payment.id,
                'transaction_id': payment.transaction_id,
                'amount': payment.amount,
                'payment_method': payment.payment_method,
                'payment_status': payment.payment_status.value,
                'payment_date': payment.payment_date.isoformat(),
                'mobile_number': payment.mobile_number,
                'description': payment.description,
                'created_at': payment.created_at.isoformat(),
                'updated_at': payment.updated_at.isoformat(),
                'payment_details': []
            }
            
            # Add payment details
            for detail in payment.payment_details:
                app = next((a for a in applications if a.id == detail.application_id), None)
                detail_dict = {
                    'id': detail.id,
                    'payment_id': detail.payment_id,
                    'application_id': detail.application_id,
                    'amount': detail.amount,
                    'created_at': detail.created_at,
                    'updated_at': detail.updated_at
                }
                
                if app:
                    detail_dict['application'] = {
                        'id': app.id,
                        'user_id': app.user_id,
                        'status': app.status.value,
                        'payment_status': app.payment_status.value,
                        'total_fee': app.total_fee
                    }
                
                result['payment_details'].append(detail_dict)
            
            return result
            
        except IntegrityError as e:
            self.db.rollback()
            raise BadRequest(f"Error creating payment: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_payment(self, payment_id: int) -> Dict[str, Any]:
        """Get payment by ID"""
        payment = self.db.query(Payment).options(
            joinedload(Payment.payment_details)
        ).filter(
            Payment.id == payment_id,
            Payment.deleted_at.is_(None)
        ).first()
        
        if not payment:
            raise NotFound(f"Payment with ID {payment_id} not found")
        
        # Format the response
        result = PaymentInDB.from_orm(payment).dict()
        
        # Add payment details
        result['payment_details'] = []
        for detail in payment.payment_details:
            app = self.db.query(Application).filter(Application.id == detail.application_id).first()
            detail_dict = {
                'id': detail.id,
                'payment_id': detail.payment_id,
                'application_id': detail.application_id,
                'amount': detail.amount,
                'created_at': detail.created_at,
                'updated_at': detail.updated_at
            }
            
            if app:
                detail_dict['application'] = {
                    'id': app.id,
                    'user_id': app.user_id,
                    'status': app.status.value,
                    'payment_status': app.payment_status.value,
                    'total_fee': app.total_fee
                }
            
            result['payment_details'].append(detail_dict)
        
        return result
    
    def get_payments(self, skip: int = 0, limit: int = 100,
                    user_id: Optional[int] = None,
                    application_id: Optional[int] = None,
                    payment_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get payments with optional filtering"""
        
        # Build base query for payments
        query = self.db.query(Payment).options(
            joinedload(Payment.payment_details)
        ).filter(Payment.deleted_at.is_(None))
        
        # Apply filters
        if payment_status:
            query = query.filter(Payment.payment_status == payment_status)
        
        # Filter by application ID
        if application_id:
            application_payments = self.db.query(PaymentDetail.payment_id).filter(
                PaymentDetail.application_id == application_id,
                PaymentDetail.deleted_at.is_(None)
            ).subquery()
            
            query = query.filter(Payment.id.in_(application_payments))
        
        # Filter by user ID (requires joining through payment details and applications)
        if user_id:
            user_applications = self.db.query(Application.id).filter(
                Application.user_id == user_id,
                Application.deleted_at.is_(None)
            ).subquery()
            
            user_payments = self.db.query(PaymentDetail.payment_id).filter(
                PaymentDetail.application_id.in_(user_applications),
                PaymentDetail.deleted_at.is_(None)
            ).subquery()
            
            query = query.filter(Payment.id.in_(user_payments))
        
        # Apply pagination and execute query
        payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
        
        # Format the response
        results = []
        for payment in payments:
            payment_dict = PaymentInDB.from_orm(payment).dict()
            payment_dict['payment_details'] = []
            
            for detail in payment.payment_details:
                app = self.db.query(Application).filter(Application.id == detail.application_id).first()
                detail_dict = {
                    'id': detail.id,
                    'payment_id': detail.payment_id,
                    'application_id': detail.application_id,
                    'amount': detail.amount,
                    'created_at': detail.created_at,
                    'updated_at': detail.updated_at
                }
                
                if app:
                    detail_dict['application'] = {
                        'id': app.id,
                        'user_id': app.user_id,
                        'status': app.status.value,
                        'payment_status': app.payment_status.value,
                        'total_fee': app.total_fee
                    }
                
                payment_dict['payment_details'].append(detail_dict)
            
            results.append(payment_dict)
        
        return results

# API Routes
@payments_bp.route('/payments', methods=['POST'])
@jwt_required()
def create_payment():
    """Create a new payment"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Get request data
        data = request.get_json()
        
        # Add created_by and updated_by if not provided
        if 'created_by' not in data:
            data['created_by'] = current_user_id
        if 'updated_by' not in data:
            data['updated_by'] = current_user_id
        
        # Create payment data object
        payment_data = PaymentCreate(**data)
        
        # Process payment
        controller = PaymentsController(db_session)
        payment = controller.create_payment(payment_data)
        
        return jsonify({
            "status": "success",
            "message": "Payment processed successfully",
            "data": payment
        }), 201
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except BadRequest as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except NotFound as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500
    finally:
        db_session.remove()

@payments_bp.route('/payments/<int:payment_id>', methods=['GET'])
@jwt_required()
def get_payment(payment_id):
    """Get a specific payment by ID"""
    try:
        controller = PaymentsController(db_session)
        payment = controller.get_payment(payment_id)
        
        return jsonify({
            "status": "success",
            "message": "Payment retrieved successfully",
            "data": payment
        }), 200
    except NotFound as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db_session.remove()

@payments_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_payments():
    """Get all payments with optional filtering"""
    try:
        # Get query parameters
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        user_id = request.args.get('user_id', type=int)
        application_id = request.args.get('application_id', type=int)
        payment_status = request.args.get('payment_status')
        
        # Get payments
        controller = PaymentsController(db_session)
        payments = controller.get_payments(
            skip=skip, 
            limit=limit,
            user_id=user_id,
            application_id=application_id,
            payment_status=payment_status
        )
        
        return jsonify({
            "status": "success",
            "message": "Payments retrieved successfully",
            "data": {
                "payments": payments,
                "pagination": {
                    "skip": skip,
                    "limit": limit,
                    "total": len(payments)  # This is not accurate for total count, but simplified for now
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db_session.remove()

@payments_bp.route('/season-applications/payment', methods=['POST'])
@jwt_required()
def process_application_payment():
    """Process payment for selected applications"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Get request data
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['application_ids', 'payment_method', 'mobile_number']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400
        
        # Get application IDs
        application_ids = data['application_ids']
        if not isinstance(application_ids, list) or not application_ids:
            return jsonify({
                "status": "error",
                "message": "application_ids must be a non-empty list"
            }), 400
        
        # Verify payment method
        payment_method_str = data['payment_method']
        payment_method_enum = None
        for method in PaymentMethod:
            if method.value == payment_method_str:
                payment_method_enum = method
                break
                
        if not payment_method_enum:
            return jsonify({
                "status": "error",
                "message": f"Invalid payment method. Valid options are: {[m.value for m in PaymentMethod]}"
            }), 400
        
        # Get applications
        applications = db_session.query(Application).filter(
            Application.id.in_(application_ids),
            Application.deleted_at.is_(None)
        ).all()
        
        if len(applications) != len(application_ids):
            found_ids = [a.id for a in applications]
            missing_ids = [aid for aid in application_ids if aid not in found_ids]
            return jsonify({
                "status": "error",
                "message": f"Some applications not found: {missing_ids}"
            }), 404
        
        # Check if any application is already paid
        paid_apps = [app.id for app in applications if app.payment_status == PaymentStatus.paid]
        if paid_apps:
            return jsonify({
                "status": "error",
                "message": f"Applications already paid: {paid_apps}"
            }), 400
        
        # Generate transaction ID
        transaction_id = ''.join(['OCPA-', 
                               ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)), 
                               '-', datetime.now().strftime("%Y%m%d%H%M%S")])
        
        # Get or calculate total amount to pay
        amount = data.get('amount', 0)
        if amount == 0:
            # Calculate total from applications
            amount = sum([app.total_fee for app in applications if app.total_fee])
            
        # Create payment record
        payment = Payment(
            transaction_id=transaction_id,
            amount=amount,
            payment_method=payment_method_enum.value,  # Use the enum value
            payment_status=PaymentStatus.paid,  # For now, assume payment is successful
            payment_date=datetime.now(),
            mobile_number=data['mobile_number'],
            description=data.get('description', f"Payment for applications {application_ids}"),
            bank_reference=data.get('bank_reference') if payment_method_enum.value == "Bank" else None,
            created_by=current_user_id,
            updated_by=current_user_id
        )
        db_session.add(payment)
        db_session.flush()
        
        # Link applications to payment through payment details
        for app in applications:
            # Create payment detail for each application
            payment_detail = PaymentDetail(
                payment_id=payment.id,
                application_id=app.id,
                amount=app.total_fee if app.total_fee else 0,
                is_active=True,
                created_by=current_user_id,
                updated_by=current_user_id
            )
            db_session.add(payment_detail)
            
            # Update application payment status
            app.payment_status = PaymentStatus.paid
            
            # Update application status if it's in pending state
            # Only change status if it's currently in pending state to avoid overriding other statuses
            if app.status == ApplicationStatus.pending:
                app.status = ApplicationStatus.approved  # Or whatever status is appropriate after payment
            
            app.updated_by = current_user_id
            app.updated_at = datetime.now()  # Ensure the updated_at field is updated
        
        db_session.commit()
        
        # Prepare response
        payment_data = {
            "payment": {
                "id": payment.id,
                "transaction_id": payment.transaction_id,
                "amount": payment.amount,
                "payment_method": payment.payment_method,
                "payment_status": payment.payment_status.value,
                "payment_date": payment.payment_date.isoformat(),
                "mobile_number": payment.mobile_number,
                "description": payment.description,
                "created_at": payment.created_at.isoformat(),
                "updated_at": payment.updated_at.isoformat()
            },
            "applications_paid": [
                {
                    "application_id": app.id,
                    "amount": app.total_fee,
                    "status": app.status.value,
                    "payment_status": app.payment_status.value
                } for app in applications
            ]
        }
        
        return jsonify({
            "status": "success",
            "message": "Payment processed successfully",
            "data": payment_data
        }), 201
        
    except Exception as e:
        db_session.rollback()
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500
    finally:
        db_session.remove()

@payments_bp.route('/test/season-applications/payment', methods=['POST'])
def test_process_application_payment():
    """Test endpoint for payment processing (no JWT required)"""
    try:
        # Get request data
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['application_ids', 'payment_method', 'mobile_number']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400
        
        # Get application IDs
        application_ids = data['application_ids']
        if not isinstance(application_ids, list) or not application_ids:
            return jsonify({
                "status": "error",
                "message": "application_ids must be a non-empty list"
            }), 400
        
        # Verify payment method
        payment_method_str = data['payment_method']
        payment_method_enum = None
        for method in PaymentMethod:
            if method.value == payment_method_str:
                payment_method_enum = method
                break
                
        if not payment_method_enum:
            return jsonify({
                "status": "error",
                "message": f"Invalid payment method. Valid options are: {[m.value for m in PaymentMethod]}"
            }), 400
        
        # Get applications
        applications = db_session.query(Application).filter(
            Application.id.in_(application_ids),
            Application.deleted_at.is_(None)
        ).all()
        
        if not applications:
            # For testing, create dummy applications if none exist
            applications = []
            for app_id in application_ids:
                app = Application(
                    id=app_id,
                    user_id=1,  # Dummy user ID
                    season_id=1,  # Dummy season ID
                    subject_id=1,  # Dummy subject ID
                    status=ApplicationStatus.pending,
                    payment_status=PaymentStatus.pending_payment,
                    total_fee=round(random.uniform(50, 200), 2),
                    created_by=1,
                    updated_by=1
                )
                applications.append(app)
        
        # Generate transaction ID
        transaction_id = ''.join(['OCPA-', 
                               ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)), 
                               '-', datetime.now().strftime("%Y%m%d%H%M%S")])
        
        # Get or calculate amount
        amount = data.get('amount', 0)
        if amount == 0:
            # Calculate total from applications
            amount = sum([app.total_fee for app in applications if app.total_fee])
            if amount == 0:
                # If still 0, set a random amount for testing
                amount = round(random.uniform(50, 200), 2)
        
        # Create payment record
        payment = Payment(
            transaction_id=transaction_id,
            amount=amount,
            payment_method=payment_method_enum.value,  # Use the enum value
            payment_status=PaymentStatus.paid,  # For testing, assume payment is successful
            payment_date=datetime.now(),
            mobile_number=data['mobile_number'],
            description=data.get('description', f"Payment for applications {application_ids}"),
            bank_reference=data.get('bank_reference') if payment_method_enum.value == "Bank" else None,
            created_by=1,  # Dummy user ID for test
            updated_by=1   # Dummy user ID for test
        )
        db_session.add(payment)
        db_session.flush()  # Get the payment ID
        
        # Link applications to payment through payment details
        for app in applications:
            # Create payment detail for each application
            payment_detail = PaymentDetail(
                payment_id=payment.id,
                application_id=app.id,
                amount=app.total_fee if app.total_fee else amount / len(applications),  # Divide amount equally if no fee
                is_active=True,
                created_by=1,  # Dummy user ID for test
                updated_by=1   # Dummy user ID for test
            )
            db_session.add(payment_detail)
            
            # Update application payment status
            app.payment_status = PaymentStatus.paid
            
            # Update application status if it's in pending state
            # Only change status if it's currently in pending state to avoid overriding other statuses
            if app.status == ApplicationStatus.pending:
                app.status = ApplicationStatus.approved  # Or whatever status is appropriate after payment
            
            app.updated_by = 1  # Dummy user ID for test
            app.updated_at = datetime.now()  # Ensure the updated_at field is updated
        
        db_session.commit()
        
        # Prepare response
        payment_data = {
            "payment": {
                "id": payment.id,
                "transaction_id": payment.transaction_id,
                "amount": payment.amount,
                "payment_method": payment.payment_method,
                "payment_status": payment.payment_status.value,
                "payment_date": payment.payment_date.isoformat(),
                "mobile_number": payment.mobile_number,
                "description": payment.description,
                "created_at": payment.created_at.isoformat(),
                "updated_at": payment.updated_at.isoformat()
            },
            "applications_paid": [
                {
                    "application_id": app.id,
                    "amount": app.total_fee,
                    "status": app.status.value,
                    "payment_status": app.payment_status.value
                } for app in applications
            ]
        }
        
        return jsonify({
            "status": "success",
            "message": "Payment processed successfully",
            "data": payment_data
        }), 201
        
    except Exception as e:
        db_session.rollback()
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500
    finally:
        db_session.remove()

@payments_bp.route('/season-applications/<int:application_id>/payment-status', methods=['GET'])
@jwt_required()
def get_application_payment_status(application_id):
    """Get payment status for a specific application"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Check if application exists
        application = db_session.query(Application).filter(
            Application.id == application_id,
            Application.is_active == True,
            Application.deleted_at.is_(None)
        ).first()
        
        if not application:
            return jsonify({
                "status": "error",
                "message": f"Application with ID {application_id} not found"
            }), 404
            
        # Removing ownership check to allow any authenticated user to view payment status
        # This makes the API more accessible for administrators and other authorized users
        
        # Get payment details for the application
        payment_details = db_session.query(PaymentDetail).filter(
            PaymentDetail.application_id == application_id,
            PaymentDetail.is_active == True,
            PaymentDetail.deleted_at.is_(None)
        ).all()
        
        payments = []
        total_paid = 0
        
        for detail in payment_details:
            payment = db_session.query(Payment).filter(
                Payment.id == detail.payment_id,
                Payment.is_active == True,
                Payment.deleted_at.is_(None)
            ).first()
            
            if payment:
                payments.append({
                    "payment_id": payment.id,
                    "transaction_id": payment.transaction_id,
                    "amount": detail.amount,
                    "payment_method": payment.payment_method,
                    "payment_status": payment.payment_status.value,
                    "payment_date": payment.payment_date.isoformat(),
                    "description": payment.description
                })
                
                if payment.payment_status == PaymentStatus.paid:
                    total_paid += detail.amount
        
        # Calculate remaining amount
        total_fee = application.total_fee or 0
        amount_remaining = max(0, total_fee - total_paid)
        
        return jsonify({
            "status": "success",
            "data": {
                "application_id": application.id,
                "payment_status": application.payment_status.value,
                "total_fee": total_fee,
                "total_paid": total_paid,
                "amount_remaining": amount_remaining,
                "is_fully_paid": application.payment_status == PaymentStatus.paid,
                "payments": payments
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500
    finally:
        db_session.remove()

@payments_bp.route('/test/season-applications/<int:application_id>/payment-status', methods=['GET'])
def test_get_application_payment_status(application_id):
    """Test endpoint to get payment status for a specific application (no JWT required)"""
    try:
        # Check if application exists
        application = db_session.query(Application).filter(
            Application.id == application_id,
            Application.is_active == True,
            Application.deleted_at.is_(None)
        ).first()
        
        if not application:
            return jsonify({
                "status": "error",
                "message": f"Application with ID {application_id} not found"
            }), 404
            
        # Get payment details for the application
        payment_details = db_session.query(PaymentDetail).filter(
            PaymentDetail.application_id == application_id,
            PaymentDetail.is_active == True,
            PaymentDetail.deleted_at.is_(None)
        ).all()
        
        payments = []
        total_paid = 0
        
        for detail in payment_details:
            payment = db_session.query(Payment).filter(
                Payment.id == detail.payment_id,
                Payment.is_active == True,
                Payment.deleted_at.is_(None)
            ).first()
            
            if payment:
                payments.append({
                    "payment_id": payment.id,
                    "transaction_id": payment.transaction_id,
                    "amount": detail.amount,
                    "payment_method": payment.payment_method,
                    "payment_status": payment.payment_status.value,
                    "payment_date": payment.payment_date.isoformat(),
                    "description": payment.description
                })
                
                if payment.payment_status == PaymentStatus.paid:
                    total_paid += detail.amount
        
        # Calculate remaining amount
        total_fee = application.total_fee or 0
        amount_remaining = max(0, total_fee - total_paid)
        
        return jsonify({
            "status": "success",
            "data": {
                "application_id": application.id,
                "payment_status": application.payment_status.value,
                "total_fee": total_fee,
                "total_paid": total_paid,
                "amount_remaining": amount_remaining,
                "is_fully_paid": application.payment_status == PaymentStatus.paid,
                "payments": payments
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500
    finally:
        db_session.remove() 