from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import get_db, db_session
from applications.models.models import (
    Application, ApplicationDetail, PaymentStatus as ApplicationPaymentStatus, 
    ApplicationStatus, Payment, PaymentDetail, PaymentMethod
)
from applications.models.schemas import ApplicationCreate, ApplicationUpdate, ApplicationInDB, MultiSubjectApplicationCreate
from applications.controllers.applications_controller import ApplicationsController
from sqlalchemy import desc
from datetime import datetime
import random
import string
from auth.middleware.token_middleware import token_refresh_middleware

# Create blueprints for application-related entities
applications_bp = Blueprint('applications_routes', __name__)
payments_bp = Blueprint('payments_routes', __name__)

# Remove per-blueprint token refresh; frontend manages token renewal

# Application routes
@applications_bp.route('/applications', methods=['GET'])
@jwt_required()
def get_applications():
    try:
        print(f"DEBUG: Getting applications")
        db = get_db()
        applications = db.query(Application).all()
        print(f"DEBUG: Found {len(applications)} applications")

        # Manual serialization instead of from_orm().dict()
        result = []
        for app in applications:
            app_dict = {
                'id': app.id,
                'user_id': app.user_id,
                'payment_status': app.payment_status.value if hasattr(app.payment_status, 'value') else app.payment_status,
                'total_fee': app.total_fee,
                'status': app.status.value if hasattr(app.status, 'value') else app.status,
                'is_active': app.is_active,
                'created_by': app.created_by,
                'updated_by': app.updated_by,
                'created_at': app.created_at,
                'updated_at': app.updated_at,
                'details': []
            }
            result.append(app_dict)

        return jsonify({
            "status": "success",
            "data": result
        })
    except Exception as e:
        print(f"DEBUG: Error in get_applications: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@applications_bp.route('/applications/<int:application_id>', methods=['GET'])
@jwt_required()
def get_application(application_id):
    try:
        print(f"DEBUG: Getting application {application_id}")
        db = get_db()
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return jsonify({
                "status": "error",
                "message": "Application not found"
            }), 404

        # Manual serialization instead of from_orm().dict()
        app_dict = {
            'id': application.id,
            'user_id': application.user_id,
            'payment_status': application.payment_status.value if hasattr(application.payment_status, 'value') else application.payment_status,
            'total_fee': application.total_fee,
            'status': application.status.value if hasattr(application.status, 'value') else application.status,
            'is_active': application.is_active,
            'created_by': application.created_by,
            'updated_by': application.updated_by,
            'created_at': application.created_at,
            'updated_at': application.updated_at,
            'details': []
        }

        return jsonify({
            "status": "success",
            "data": app_dict
        })
    except Exception as e:
        print(f"DEBUG: Error in get_application: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@applications_bp.route('/applications', methods=['POST'])
def create_application():
    """Create a new application"""
    try:
        print(f"DEBUG: Starting create_application endpoint")

        # Get and validate request data
        data = request.get_json()
        print(f"DEBUG: Received data: {data}")
        print(f"DEBUG: Creating ApplicationCreate with data")
        application_data = ApplicationCreate(**data)
        print(f"DEBUG: ApplicationCreate created successfully")

        # Use user_id from request data (no JWT required for now)
        current_user_id = application_data.user_id
        print(f"DEBUG: Using user ID from request: {current_user_id}")

        # Create application using the controller
        print(f"DEBUG: Creating application with controller")
        controller = ApplicationsController(db_session)
        application = controller.create_application(application_data)
        print(f"DEBUG: Application created successfully: {application}")
        return jsonify({
            "status": "success",
            "data": application
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@applications_bp.route('/applications/<int:application_id>', methods=['PUT'])
@jwt_required()
def update_application(application_id):
    try:
        db = get_db()
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return jsonify({
                "status": "error",
                "message": "Application not found"
            }), 404
        
        data = request.get_json()
        application_data = ApplicationUpdate(**data)
        
        for key, value in application_data.dict(exclude_unset=True).items():
            setattr(application, key, value)
        
        db.commit()
        db.refresh(application)
        return jsonify({
            "status": "success",
            "data": {
                'id': application.id,
                'user_id': application.user_id,
                'payment_status': application.payment_status.value if hasattr(application.payment_status, 'value') else application.payment_status,
                'total_fee': application.total_fee,
                'status': application.status.value if hasattr(application.status, 'value') else application.status,
                'is_active': application.is_active,
                'created_by': application.created_by,
                'updated_by': application.updated_by,
                'created_at': application.created_at,
                'updated_at': application.updated_at,
                'details': []
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@applications_bp.route('/my-applications', methods=['GET'])
@jwt_required()
def get_my_applications():
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get total count
        total_count = db.query(Application).filter(Application.user_id == current_user_id).count()
        
        # Get paginated applications
        applications = db.query(Application)\
            .filter(Application.user_id == current_user_id)\
            .order_by(desc(Application.created_at))\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            "status": "success",
            "data": {
                "applications": [{
                    'id': app.id,
                    'user_id': app.user_id,
                    'payment_status': app.payment_status.value if hasattr(app.payment_status, 'value') else app.payment_status,
                    'total_fee': app.total_fee,
                    'status': app.status.value if hasattr(app.status, 'value') else app.status,
                    'is_active': app.is_active,
                    'created_by': app.created_by,
                    'updated_by': app.updated_by,
                    'created_at': app.created_at,
                    'updated_at': app.updated_at,
                    'details': []
                } for app in applications],
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total_count + per_page - 1) // per_page
                }
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@applications_bp.route('/my-applications/<int:application_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_my_application(application_id):
    """Cancel an application by updating status to withdrawn"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        # Find the application belonging to the current user
        application = db.query(Application).filter(
            Application.id == application_id,
            Application.user_id == current_user_id,
            Application.deleted_at.is_(None)
        ).first()
        
        if not application:
            return jsonify({
                "status": "error",
                "message": "Application not found or you don't have permission to cancel this application"
            }), 404
        
        # Check if application can be cancelled (not already withdrawn, rejected, or verified)
        if application.status in [ApplicationStatus.withdrawn, ApplicationStatus.rejected, ApplicationStatus.verified]:
            return jsonify({
                "status": "error",
                "message": f"Application cannot be cancelled. Current status: {application.status.value}"
            }), 400
        
        # Hard delete the application and all its details
        # First delete all application details (due to foreign key constraints)
        for detail in application.details:
            db.delete(detail)
        
        # Then delete the application
        db.delete(application)
        
        db.commit()
        
        return jsonify({
            "status": "success",
            "message": "Application cancelled successfully",
            "data": {
                "id": application_id,
                "status": "deleted",
                "message": "Application and all details have been permanently removed"
            }
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@applications_bp.route('/season-applications', methods=['GET'])
@jwt_required()
def get_season_applications():
    """Get applications for a season with optional filtering"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate skip based on page and per_page
        skip = (page - 1) * per_page
        limit = per_page
        
        # Required season_id parameter
        season_id = request.args.get('season_id', type=int)
        if not season_id:
            return jsonify({
                "status": "error",
                "message": "Missing required parameter: season_id"
            }), 400
            
        # Optional filters
        user_id = request.args.get('user_id', type=int)
        subject_id = request.args.get('subject_id', type=int)
        status = request.args.get('status')
        payment_status = request.args.get('payment_status')
        
        # Validate status and payment_status if provided
        if status and status not in [s.value for s in ApplicationStatus]:
            return jsonify({
                "status": "error",
                "message": f"Invalid status. Must be one of {[s.value for s in ApplicationStatus]}"
            }), 400
        
        if payment_status and payment_status not in [s.value for s in ApplicationPaymentStatus]:
            return jsonify({
                "status": "error",
                "message": f"Invalid payment status. Must be one of {[s.value for s in ApplicationPaymentStatus]}"
            }), 400
        
        # Get total count for pagination
        controller = ApplicationsController(db_session)
        
        # Base query for count
        count_query = db_session.query(Application).filter(
            Application.deleted_at.is_(None)
        )
        
        # Add user filter if provided
        if user_id:
            count_query = count_query.filter(Application.user_id == user_id)
        
        # Apply filters that need to join with ApplicationDetail
        if season_id or subject_id:
            # Start with all application IDs
            query = db_session.query(Application.id).filter(
                Application.deleted_at.is_(None)
            )
            
            # Apply user filter if provided
            if user_id:
                query = query.filter(Application.user_id == user_id)
                
            application_ids = set(row[0] for row in query)
            
            # If filtered by season, find matching applications
            if season_id:
                season_app_ids = set(row[0] for row in db_session.query(ApplicationDetail.application_id).filter(
                    ApplicationDetail.season_id == season_id,
                    ApplicationDetail.deleted_at.is_(None)
                ))
                application_ids &= season_app_ids
            
            # If filtered by subject, find matching applications
            if subject_id:
                subject_app_ids = set(row[0] for row in db_session.query(ApplicationDetail.application_id).filter(
                    ApplicationDetail.subject_id == subject_id,
                    ApplicationDetail.deleted_at.is_(None)
                ))
                application_ids &= subject_app_ids
            
            # Add the ID filter to the main query
            if application_ids:
                count_query = count_query.filter(Application.id.in_(application_ids))
            else:
                # If no applications match the criteria, return empty result
                return jsonify({
                    "status": "success",
                    "message": "No applications found matching the criteria",
                    "data": {
                        "seasons": [],
                        "pagination": {
                            "page": page,
                            "per_page": per_page,
                            "total_items": 0,
                            "total_pages": 0,
                            "has_next": False,
                            "has_prev": False
                        }
                    }
                }), 200
        
        # Apply direct filters on Application
        if status:
            count_query = count_query.filter(Application.status == status)
        if payment_status:
            count_query = count_query.filter(Application.payment_status == payment_status)
            
        # Get total count
        total_count = count_query.count()
        
        # Get applications with pagination
        applications = controller.get_applications(
            skip=skip, 
            limit=limit,
            user_id=user_id,  # Filter by the current user
            season_id=season_id,
            subject_id=subject_id,
            status=status,
            payment_status=payment_status
        )
        
        # Calculate pagination metadata
        total_pages = (total_count + per_page - 1) // per_page  # Ceiling division
        has_next = page < total_pages
        has_prev = page > 1
        
        return jsonify({
            "status": "success",
            "message": "Season applications retrieved successfully",
            "data": {
                "applications": applications,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev
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

@applications_bp.route('/season-applications', methods=['POST'])
@jwt_required()
def create_season_application():
    """Create a new application for a season with multiple subjects"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Get and validate request data
        data = request.get_json()
        application_data = MultiSubjectApplicationCreate(
            user_id=current_user_id,
            subject_ids=data['subject_ids'],
            payment_status=data.get('payment_status', 'pending_payment'),
            status=data.get('status', 'pending'),
            created_by=current_user_id,
            updated_by=current_user_id
        )
        
        # Create application using the controller
        controller = ApplicationsController(db_session)
        application = controller.create_season_applications(
            user_id=application_data.user_id,
            subject_ids=application_data.subject_ids,
            payment_status=application_data.payment_status,
            status=application_data.status,
            created_by=application_data.created_by,
            updated_by=application_data.updated_by
        )
        
        return jsonify({
            "status": "success",
            "message": "Season application created successfully",
            "data": application
        }), 201
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db_session.remove()

# Payment routes
@payments_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_payments():
    try:
        db = get_db()
        payments = db.query(ApplicationPaymentStatus).all()
        return jsonify({
            "status": "success",
            "data": [{"id": p.id, "status": p.value} for p in payments]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@payments_bp.route('/payments/<int:payment_id>', methods=['GET'])
@jwt_required()
def get_payment(payment_id):
    try:
        db = get_db()
        payment = db.query(ApplicationPaymentStatus).filter(ApplicationPaymentStatus.id == payment_id).first()
        if not payment:
            return jsonify({
                "status": "error",
                "message": "Payment not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": {"id": payment.id, "status": payment.value}
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@payments_bp.route('/payments', methods=['POST'])
@jwt_required()
def create_payment():
    try:
        db = get_db()
        data = request.get_json()
        payment = ApplicationPaymentStatus(value=data.get('status'))
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return jsonify({
            "status": "success",
            "data": {"id": payment.id, "status": payment.value}
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@payments_bp.route('/season-applications/payment', methods=['POST'])
@jwt_required()
def process_application_payment():
    """Process payment for selected applications"""
    try:
        # Get request data
        data = request.get_json()
        current_user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['application_ids', 'payment_method', 'mobile_number']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400
                
        # Get payment method
        payment_method = data.get('payment_method')
        if payment_method:
            # Convert to enum - schema validation has already verified this is valid
            payment_method = PaymentMethod(payment_method)
                
        # Verify that applications exist and belong to the user
        application_ids = data['application_ids']
        if not application_ids:
            return jsonify({
                "status": "error",
                "message": "No application IDs provided"
            }), 400
            
        # Verify applications exist
        applications = db_session.query(Application).filter(
            Application.id.in_(application_ids),
            Application.user_id == current_user_id,
            Application.is_active == True,
            Application.deleted_at.is_(None)
        ).all()
        
        if len(applications) != len(application_ids):
            return jsonify({
                "status": "error",
                "message": "One or more applications do not exist or do not belong to the current user"
            }), 404
            
        # Generate transaction ID
        transaction_id = ''.join(['OCPA-', 
                                ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)), 
                                '-', datetime.now().strftime("%Y%m%d%H%M%S")])
        
        # Generate bank reference number based on payment method
        bank_reference = None
        if payment_method == PaymentMethod.bank:
            # For bank payments, use the reference from the payload
            bank_reference = data.get('bank_reference')
            if not bank_reference:
                return jsonify({
                    "status": "error",
                    "message": "Bank reference is required for bank payments"
                }), 400
        elif payment_method == PaymentMethod.mpesa:
            bank_reference = f"MP{transaction_id[-12:]}"
        elif payment_method == PaymentMethod.airtel:
            bank_reference = f"AM{transaction_id[-12:]}"
        elif payment_method == PaymentMethod.mixx:
            bank_reference = f"MX{transaction_id[-12:]}"
        elif payment_method == PaymentMethod.card:
            bank_reference = f"CD{transaction_id[-12:]}"
        elif payment_method == PaymentMethod.cash:
            bank_reference = f"CS{transaction_id[-12:]}"
        else:
            bank_reference = f"OT{transaction_id[-12:]}"
        
        # Get or calculate total amount to pay
        amount = data.get('amount', 0)
        if amount == 0:
            # Calculate total from applications
            amount = sum([app.total_fee for app in applications if app.total_fee])
            
        # Determine if this is an MNO payment
        is_mno_payment = payment_method in [PaymentMethod.mpesa, PaymentMethod.mixx, PaymentMethod.airtel]
            
        # Create payment record - always set payment_status to paid
        payment = Payment(
            transaction_id=transaction_id,
            amount=amount,
            payment_method=payment_method.value,  # Store the string value instead of the enum object
            payment_status=ApplicationPaymentStatus.paid,  # Always set to paid for the payment record
            payment_date=datetime.now(),
            mobile_number=data['mobile_number'],
            description=data.get('description', f"Payment for applications {application_ids}"),
            bank_reference=bank_reference,  # Add the bank reference
            created_by=current_user_id,
            updated_by=current_user_id
        )
        db_session.add(payment)
        db_session.flush()  # Get the payment ID
        
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
            
            # Update application payment status to paid
            app.payment_status = ApplicationPaymentStatus.paid
            
            # Update application status based on payment method
            if is_mno_payment:
                # For MNO payments, set status to approved
                app.status = ApplicationStatus.approved
            else:
                # For non-MNO payments, set status to pending
                app.status = ApplicationStatus.pending
            
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
                
                if payment.payment_status == ApplicationPaymentStatus.paid:
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
                "is_fully_paid": application.payment_status == ApplicationPaymentStatus.paid,
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