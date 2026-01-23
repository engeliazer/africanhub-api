from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional, Dict, Any
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.sql import text

from applications.models.models import Application, ApplicationDetail, PaymentStatus, ApplicationStatus
from applications.models.schemas import ApplicationCreate, ApplicationUpdate, ApplicationInDB
from subjects.models.models import Subject
from auth.models.models import User
from database.db_connector import db_session

applications_bp = Blueprint('applications_controller', __name__)

class ApplicationsController:
    def __init__(self, db: Session):
        self.db = db
    
    def create_application(self, application: ApplicationCreate) -> Dict[str, Any]:
        """Create a new application with details"""
        try:
            # Verify user exists
            user = self.db.query(User).filter(User.id == application.user_id).first()
            if not user:
                raise BadRequest(f"User with ID {application.user_id} not found")
            
            # Create the main application
            db_application = Application(
                user_id=application.user_id,
                payment_status=application.payment_status,
                total_fee=application.total_fee,
                status=application.status,
                is_active=application.is_active,
                created_by=application.created_by,
                updated_by=application.updated_by
            )
            
            self.db.add(db_application)
            self.db.flush()  # This assigns an ID to db_application
            
            # Process each detail
            total_fee = 0
            for detail in application.details:
                # Verify subject exists
                subject = self.db.query(Subject).filter(
                    Subject.id == detail.subject_id,
                    Subject.is_active == True
                ).first()
                if not subject:
                    raise BadRequest(f"Subject with ID {detail.subject_id} not found or not active")
                
                # Check if application detail already exists
                existing_detail = self.db.query(ApplicationDetail).join(Application).filter(
                    Application.user_id == application.user_id,
                    ApplicationDetail.subject_id == detail.subject_id,
                    ApplicationDetail.deleted_at.is_(None)
                ).first()
                
                if existing_detail:
                    raise BadRequest(f"Application already exists for user and subject {detail.subject_id}")
                
                # Set fee from subject if not provided
                fee = detail.fee if detail.fee is not None else subject.current_price or 0
                total_fee += fee
                
                # Create detail
                db_detail = ApplicationDetail(
                    application_id=db_application.id,
                    subject_id=detail.subject_id,
                    fee=fee,
                    status=detail.status,
                    is_active=detail.is_active,
                    created_by=application.created_by,
                    updated_by=application.updated_by
                )
                
                self.db.add(db_detail)
            
            # Update the total fee on the application
            db_application.total_fee = total_fee
            
            self.db.commit()
            self.db.refresh(db_application)
            
            # Reload with details
            application_with_details = self.db.query(Application).options(
                joinedload(Application.details).joinedload(ApplicationDetail.subject),
                joinedload(Application.user)
            ).filter(Application.id == db_application.id).first()
            
            # Format the response manually to avoid serialization issues
            result = {
                'id': application_with_details.id,
                'user_id': application_with_details.user_id,
                'payment_status': application_with_details.payment_status.value,
                'total_fee': application_with_details.total_fee,
                'status': application_with_details.status.value,
                'is_active': application_with_details.is_active,
                'created_by': application_with_details.created_by,
                'updated_by': application_with_details.updated_by,
                'created_at': application_with_details.created_at,
                'updated_at': application_with_details.updated_at,
                'details': []
            }
            
            # Add details
            for db_detail in application_with_details.details:
                detail_dict = {
                    'id': db_detail.id,
                    'application_id': db_detail.application_id,
                    'subject_id': db_detail.subject_id,
                    'fee': db_detail.fee,
                    'status': db_detail.status.value,
                    'is_active': db_detail.is_active,
                    'created_by': db_detail.created_by,
                    'updated_by': db_detail.updated_by,
                    'created_at': db_detail.created_at,
                    'updated_at': db_detail.updated_at
                }
                result['details'].append(detail_dict)
            
            # Add user details
            if application_with_details.user:
                result['user_details'] = {
                    'id': application_with_details.user.id,
                    'email': application_with_details.user.email,
                    'first_name': application_with_details.user.first_name,
                    'last_name': application_with_details.user.last_name,
                    'phone': application_with_details.user.phone
                }
            
            # Add details for each subject/season
            for i, detail in enumerate(result['details']):
                # Get the season and subject from the DB object
                db_detail = application_with_details.details[i]
                
                # Add subject details
                if db_detail.subject:
                    detail['subject_details'] = {
                        'id': db_detail.subject.id,
                        'name': db_detail.subject.name,
                        'current_price': getattr(db_detail.subject, 'current_price', None),
                        'description': getattr(db_detail.subject, 'description', None)
                    }
            
            return result
            
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Error creating application due to integrity constraint")
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_application(self, application_id: int) -> Dict[str, Any]:
        """Get application by ID"""
        application = self.db.query(Application).options(
            joinedload(Application.user),
            joinedload(Application.details).joinedload(ApplicationDetail.subject)
        ).filter(
            Application.id == application_id,
            Application.deleted_at.is_(None)
        ).first()
        
        if not application:
            raise NotFound(f"Application with ID {application_id} not found")
        
        # Format the response
        result = ApplicationInDB.from_orm(application).dict()
        
        # Add user details
        if application.user:
            result['user_details'] = {
                'id': application.user.id,
                'email': application.user.email,
                'first_name': application.user.first_name,
                'last_name': application.user.last_name,
                'phone': application.user.phone
            }
        
        # Add details for each subject
        for i, detail in enumerate(result['details']):
            # Get the subject from the DB object
            db_detail = application.details[i]
            
            # Add subject details
            if db_detail.subject:
                detail['subject_details'] = {
                    'id': db_detail.subject.id,
                    'name': db_detail.subject.name,
                    'current_price': getattr(db_detail.subject, 'current_price', None),
                    'description': getattr(db_detail.subject, 'description', None)
                }
        
        return result
    
    def get_applications(self, skip: int = 0, limit: int = 100, 
                        user_id: Optional[int] = None,
                        subject_id: Optional[int] = None,
                        status: Optional[str] = None,
                        payment_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get applications with optional filtering"""
        
        # Build base query for applications
        query = self.db.query(Application).options(
            joinedload(Application.user),
            joinedload(Application.details).joinedload(ApplicationDetail.season),
            joinedload(Application.details).joinedload(ApplicationDetail.subject)
        ).filter(Application.deleted_at.is_(None))
        
        # Apply filters directly on Application model
        if user_id:
            query = query.filter(Application.user_id == user_id)
        
        if payment_status:
            # Convert string to enum if needed
            if isinstance(payment_status, str):
                try:
                    payment_status_enum = PaymentStatus[payment_status]
                    query = query.filter(Application.payment_status == payment_status_enum)
                except KeyError:
                    # If invalid enum value, try direct comparison (in case it's the enum value string)
                    query = query.filter(Application.payment_status == payment_status)
            else:
                query = query.filter(Application.payment_status == payment_status)
        
        if status:
            # Convert string to enum if needed
            if isinstance(status, str):
                try:
                    status_enum = ApplicationStatus[status]
                    query = query.filter(Application.status == status_enum)
                except KeyError:
                    # If invalid enum value, try direct comparison (in case it's the enum value string)
                    query = query.filter(Application.status == status)
            else:
                query = query.filter(Application.status == status)
        
        # Apply filters that need to join with ApplicationDetail
        if subject_id:
            # Start with all application IDs
            application_ids = set(row[0] for row in self.db.query(Application.id).filter(
                Application.deleted_at.is_(None)
            ))
            
            # If filtered by subject, find matching applications
            subject_app_ids = set(row[0] for row in self.db.query(ApplicationDetail.application_id).filter(
                ApplicationDetail.subject_id == subject_id,
                ApplicationDetail.deleted_at.is_(None)
            ))
            application_ids &= subject_app_ids
            
            # Add the ID filter to the main query
            if application_ids:
                query = query.filter(Application.id.in_(application_ids))
            else:
                # If no applications match the criteria, return empty list
                return []
        
        # Apply pagination and execute query
        applications = query.order_by(Application.created_at.desc()).offset(skip).limit(limit).all()
        
        # Debug: Print the original query results
        print(f"DEBUG get_applications: Found {len(applications)} applications in database query")
        for app in applications:
            print(f"DEBUG get_applications: App ID={app.id}, Status={app.status.value}, Payment={app.payment_status.value}")
        
        # Format the response
        results = []
        for application in applications:
            # Convert to dict - manually to preserve status values
            app_dict = {
                'id': application.id,
                'user_id': application.user_id,
                'payment_status': application.payment_status.value,  # Use .value to get string
                'total_fee': application.total_fee,
                'status': application.status.value,  # Use .value to get string
                'is_active': application.is_active,
                'created_by': application.created_by,
                'updated_by': application.updated_by,
                'created_at': application.created_at,
                'updated_at': application.updated_at,
                'details': []
            }
            
            # Add user details
            if application.user:
                app_dict['user_details'] = {
                    'id': application.user.id,
                    'email': application.user.email,
                    'first_name': application.user.first_name,
                    'last_name': application.user.last_name,
                    'phone': application.user.phone
                }
            
            # Add details for each subject
            for db_detail in application.details:
                detail = {
                    'id': db_detail.id,
                    'application_id': db_detail.application_id,
                    'subject_id': db_detail.subject_id,
                    'fee': db_detail.fee,
                    'status': db_detail.status.value,  # Use .value to get string
                    'is_active': db_detail.is_active,
                    'created_by': db_detail.created_by,
                    'updated_by': db_detail.updated_by,
                    'created_at': db_detail.created_at,
                    'updated_at': db_detail.updated_at
                }
                
                # Add subject details
                if db_detail.subject:
                    detail['subject_details'] = {
                        'id': db_detail.subject.id,
                        'name': db_detail.subject.name,
                        'current_price': getattr(db_detail.subject, 'current_price', None),
                        'description': getattr(db_detail.subject, 'description', None)
                    }
                else:
                    detail['subject_details'] = {
                        'id': detail.get('subject_id'),
                        'name': 'Unknown Subject',
                        'current_price': None,
                        'description': None
                    }
                
                app_dict['details'].append(detail)
            
            results.append(app_dict)
        
        print(f"DEBUG get_applications: Returning {len(results)} applications after formatting")
        return results
    
    def update_application(self, application_id: int, application_update: ApplicationUpdate) -> Dict[str, Any]:
        """Update an existing application"""
        db_application = self.db.query(Application).filter(
            Application.id == application_id,
            Application.deleted_at.is_(None)
        ).first()
        
        if not db_application:
            raise NotFound(f"Application with ID {application_id} not found")
        
        # Update user if provided
        if application_update.user_id is not None:
            user = self.db.query(User).filter(User.id == application_update.user_id).first()
            if not user:
                raise BadRequest(f"User with ID {application_update.user_id} not found")
            db_application.user_id = application_update.user_id
        
        # Update other fields if provided
        if application_update.payment_status is not None:
            db_application.payment_status = application_update.payment_status
        
        if application_update.total_fee is not None:
            db_application.total_fee = application_update.total_fee
        
        if application_update.status is not None:
            db_application.status = application_update.status
        
        if application_update.is_active is not None:
            db_application.is_active = application_update.is_active
        
        # Always update the updated_by and updated_at fields
        db_application.updated_by = application_update.updated_by
        db_application.updated_at = datetime.utcnow()
        
        try:
            self.db.commit()
            
            # Reload with details
            application_with_details = self.db.query(Application).options(
                joinedload(Application.details).joinedload(ApplicationDetail.subject),
                joinedload(Application.user)
            ).filter(Application.id == db_application.id).first()
            
            # Format the response manually to avoid serialization issues
            result = {
                'id': application_with_details.id,
                'user_id': application_with_details.user_id,
                'payment_status': application_with_details.payment_status.value,
                'total_fee': application_with_details.total_fee,
                'status': application_with_details.status.value,
                'is_active': application_with_details.is_active,
                'created_by': application_with_details.created_by,
                'updated_by': application_with_details.updated_by,
                'created_at': application_with_details.created_at,
                'updated_at': application_with_details.updated_at,
                'details': []
            }
            
            # Add details
            for db_detail in application_with_details.details:
                detail_dict = {
                    'id': db_detail.id,
                    'application_id': db_detail.application_id,
                    'subject_id': db_detail.subject_id,
                    'fee': db_detail.fee,
                    'status': db_detail.status.value,
                    'is_active': db_detail.is_active,
                    'created_by': db_detail.created_by,
                    'updated_by': db_detail.updated_by,
                    'created_at': db_detail.created_at,
                    'updated_at': db_detail.updated_at
                }
                result['details'].append(detail_dict)
            
            # Add user details
            if application_with_details.user:
                result['user_details'] = {
                    'id': application_with_details.user.id,
                    'email': application_with_details.user.email,
                    'first_name': application_with_details.user.first_name,
                    'last_name': application_with_details.user.last_name,
                    'phone': application_with_details.user.phone
                }
            
            # Add details for each subject/season
            for i, detail in enumerate(result['details']):
                # Get the season and subject from the DB object
                db_detail = application_with_details.details[i]
                
                # Add subject details
                if db_detail.subject:
                    detail['subject_details'] = {
                        'id': db_detail.subject.id,
                        'name': db_detail.subject.name,
                        'current_price': getattr(db_detail.subject, 'current_price', None),
                        'description': getattr(db_detail.subject, 'description', None)
                    }
            
            return result
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Error updating application due to integrity constraint")
        except Exception as e:
            self.db.rollback()
            raise e
    
    def delete_application(self, application_id: int, deleted_by: int) -> bool:
        """Soft delete an application"""
        db_application = self.db.query(Application).filter(
            Application.id == application_id,
            Application.deleted_at.is_(None)
        ).first()
        
        if not db_application:
            raise NotFound(f"Application with ID {application_id} not found")
        
        db_application.deleted_at = datetime.utcnow()
        db_application.deleted_by = deleted_by
        db_application.is_active = False
        
        try:
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e
    
    def create_season_applications(self, user_id: int, subject_ids: List[int], 
                                 payment_status: str, status: str, created_by: int, updated_by: int) -> Dict[str, Any]:
        """Create an application for a user with multiple subjects for a single season"""
        try:
            # Verify user exists
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise BadRequest(f"User with ID {user_id} not found")
            
            # Get all specified subjects and verify they exist
            subjects = self.db.query(Subject).filter(
                Subject.id.in_(subject_ids),
                Subject.is_active == True
            ).all()
            
            if len(subjects) != len(subject_ids):
                found_ids = [s.id for s in subjects]
                missing_ids = [sid for sid in subject_ids if sid not in found_ids]
                raise BadRequest(f"Some subjects not found or not active: {missing_ids}")
            
            # Check for existing active applications for this user/subjects
            existing_details = self.db.query(ApplicationDetail).join(Application).filter(
                Application.user_id == user_id,
                ApplicationDetail.subject_id.in_(subject_ids),
                Application.is_active == True,
                ApplicationDetail.is_active == True,
                Application.deleted_at.is_(None),
                ApplicationDetail.deleted_at.is_(None)
            ).all()
            
            existing_subject_ids = [detail.subject_id for detail in existing_details]
            new_subject_ids = [sid for sid in subject_ids if sid not in existing_subject_ids]
            
            # Validate before any database modifications
            if not new_subject_ids:
                raise BadRequest("Applications already exist for all specified subjects in this season")
            
            # Create new application
            application = Application(
                user_id=user_id,
                payment_status=payment_status,
                status=status,
                is_active=True,
                created_by=created_by,
                updated_by=updated_by
            )
            
            self.db.add(application)
            self.db.flush()  # Flush to get the application ID
            
            # Calculate total fee and create details for new subjects
            total_fee = 0
            
            for subject in subjects:
                if subject.id not in new_subject_ids:
                    continue
                
                fee = subject.current_price or 0
                total_fee += fee
                
                # Create application detail
                detail = ApplicationDetail(
                    application_id=application.id,
                    subject_id=subject.id,
                    fee=fee,
                    status=status,
                    is_active=True,
                    created_by=created_by,
                    updated_by=updated_by
                )
                
                self.db.add(detail)
            
            # Update the total fee
            application.total_fee = total_fee
            
            self.db.commit()
            
            # Reload the application with all details
            application_with_details = self.db.query(Application).options(
                joinedload(Application.details).joinedload(ApplicationDetail.subject),
                joinedload(Application.user)
            ).filter(Application.id == application.id).first()
            
            # Format the response manually to avoid serialization issues
            result = {
                'id': application_with_details.id,
                'user_id': application_with_details.user_id,
                'payment_status': application_with_details.payment_status.value,
                'total_fee': application_with_details.total_fee,
                'status': application_with_details.status.value,
                'is_active': application_with_details.is_active,
                'created_by': application_with_details.created_by,
                'updated_by': application_with_details.updated_by,
                'created_at': application_with_details.created_at,
                'updated_at': application_with_details.updated_at,
                'details': []
            }
            
            # Add details
            for db_detail in application_with_details.details:
                detail_dict = {
                    'id': db_detail.id,
                    'application_id': db_detail.application_id,
                    'subject_id': db_detail.subject_id,
                    'fee': db_detail.fee,
                    'status': db_detail.status.value,
                    'is_active': db_detail.is_active,
                    'created_by': db_detail.created_by,
                    'updated_by': db_detail.updated_by,
                    'created_at': db_detail.created_at,
                    'updated_at': db_detail.updated_at
                }
                result['details'].append(detail_dict)
            
            # Add user details
            if application_with_details.user:
                result['user_details'] = {
                    'id': application_with_details.user.id,
                    'email': application_with_details.user.email,
                    'first_name': application_with_details.user.first_name,
                    'last_name': application_with_details.user.last_name,
                    'phone': application_with_details.user.phone
                }
            
            # Add details for each subject/season
            for i, detail in enumerate(result['details']):
                # Get the season and subject from the DB object
                db_detail = application_with_details.details[i]
                
                # Add subject details
                if db_detail.subject:
                    detail['subject_details'] = {
                        'id': db_detail.subject.id,
                        'name': db_detail.subject.name,
                        'current_price': getattr(db_detail.subject, 'current_price', None),
                        'description': getattr(db_detail.subject, 'description', None)
                    }
            
            return result
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"IntegrityError details: {str(e)}")
            raise BadRequest(f"Error creating applications due to integrity constraint: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise e

# API Routes
@applications_bp.route('/applications', methods=['POST'])
@jwt_required()
def create_application():
    """Create a new application"""
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
        
        # Create application data object
        application_data = ApplicationCreate(**data)
        
        # Process application
        controller = ApplicationsController(db_session)
        application = controller.create_application(application_data)
        
        return jsonify({
            "status": "success",
            "message": "Application created successfully",
            "data": application
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
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@applications_bp.route('/applications', methods=['GET'])
@jwt_required()
def get_applications():
    """Get all applications with optional filtering"""
    try:
        # Get query parameters
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        user_id = request.args.get('user_id', type=int)
        season_id = request.args.get('season_id', type=int)
        subject_id = request.args.get('subject_id', type=int)
        status = request.args.get('status')
        payment_status = request.args.get('payment_status')
        
        # Validate status and payment_status if provided
        if status and status not in [s.value for s in ApplicationStatus]:
            return jsonify({
                "status": "error",
                "message": f"Invalid status. Must be one of {[s.value for s in ApplicationStatus]}"
            }), 400
        
        if payment_status and payment_status not in [s.value for s in PaymentStatus]:
            return jsonify({
                "status": "error",
                "message": f"Invalid payment status. Must be one of {[s.value for s in PaymentStatus]}"
            }), 400
        
        # Get applications
        controller = ApplicationsController(db_session)
        applications = controller.get_applications(
            skip=skip, 
            limit=limit,
            user_id=user_id,
            season_id=season_id,
            subject_id=subject_id,
            status=status,
            payment_status=payment_status
        )
        
        return jsonify({
            "status": "success",
            "message": "Applications retrieved successfully",
            "data": {
                "applications": applications,
                "pagination": {
                    "skip": skip,
                    "limit": limit,
                    "total": len(applications)  # This is not accurate for total count, but simplified for now
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@applications_bp.route('/applications/<int:application_id>', methods=['GET'])
@jwt_required()
def get_application(application_id):
    """Get a specific application by ID"""
    try:
        controller = ApplicationsController(db_session)
        application = controller.get_application(application_id)
        
        return jsonify({
            "status": "success",
            "message": "Application retrieved successfully",
            "data": application
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

@applications_bp.route('/applications/<int:application_id>', methods=['PUT'])
@jwt_required()
def update_application(application_id):
    """Update a specific application"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Get request data
        data = request.get_json()
        
        # Add updated_by if not provided
        if 'updated_by' not in data:
            data['updated_by'] = current_user_id
        
        # Create application update data object
        application_data = ApplicationUpdate(**data)
        
        # Update application
        controller = ApplicationsController(db_session)
        application = controller.update_application(application_id, application_data)
        
        return jsonify({
            "status": "success",
            "message": "Application updated successfully",
            "data": application.dict()
        }), 200
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except NotFound as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404
    except BadRequest as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@applications_bp.route('/applications/<int:application_id>', methods=['DELETE'])
@jwt_required()
def delete_application(application_id):
    """Soft delete a specific application"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Delete application
        controller = ApplicationsController(db_session)
        success = controller.delete_application(application_id, current_user_id)
        
        return jsonify({
            "status": "success",
            "message": "Application deleted successfully"
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

@applications_bp.route('/test-fixed-my-applications', methods=['GET'])
def test_fixed_my_applications():
    """Test version of get_my_applications without authentication requirement"""
    try:
        # Hardcoded user ID
        current_user_id = 1
        
        # Get query parameters for pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        # Optional filters
        season_id = request.args.get('season_id', type=int)
        subject_id = request.args.get('subject_id', type=int)
        status = request.args.get('status')
        payment_status = request.args.get('payment_status')
        
        # Validate status and payment_status if provided
        if status and status not in [s.value for s in ApplicationStatus]:
            return jsonify({
                "status": "error",
                "message": f"Invalid status. Must be one of {[s.value for s in ApplicationStatus]}"
            }), 400
        
        if payment_status and payment_status not in [s.value for s in PaymentStatus]:
            return jsonify({
                "status": "error",
                "message": f"Invalid payment status. Must be one of {[s.value for s in PaymentStatus]}"
            }), 400
            
        # Build WHERE clause dynamically based on filters
        where_clauses = ["a.user_id = :user_id", "a.deleted_at IS NULL"]
        params = {"user_id": current_user_id, "limit": per_page, "offset": offset}
        
        if status:
            where_clauses.append("a.status = :status")
            params["status"] = status
            
        if payment_status:
            where_clauses.append("a.payment_status = :payment_status")
            params["payment_status"] = payment_status
            
        # Create application ID filter for season/subject
        if season_id or subject_id:
            # Build subquery for filtering by season/subject
            subquery_clauses = ["ad.deleted_at IS NULL"]
            
            if season_id:
                subquery_clauses.append("ad.season_id = :season_id")
                params["season_id"] = season_id
                
            if subject_id:
                subquery_clauses.append("ad.subject_id = :subject_id")
                params["subject_id"] = subject_id
                
            # Add the subquery to filter application IDs
            where_clauses.append(f"a.id IN (SELECT application_id FROM application_details ad WHERE {' AND '.join(subquery_clauses)})")
        
        # Combine all WHERE clauses
        where_clause = " AND ".join(where_clauses)
        
        # Query to count total matching applications
        count_query = f"""
        SELECT COUNT(*) as total
        FROM applications a
        WHERE {where_clause}
        """
        
        # Execute count query
        result = db_session.execute(text(count_query), params).first()
        total_count = result.total if result else 0
        
        # Calculate pagination metadata
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1
        
        # No applications found
        if total_count == 0:
            return jsonify({
                "status": "success",
                "message": "No applications found",
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
        
        # Main query to get applications with pagination
        query = f"""
        SELECT 
            a.id, a.user_id, a.payment_status, a.total_fee, a.status, a.created_at, a.updated_at,
            u.id as user_id, u.email, u.first_name, u.last_name, u.phone
        FROM 
            applications a 
        INNER JOIN 
            users u ON a.user_id = u.id 
        WHERE 
            {where_clause}
        ORDER BY 
            a.created_at DESC
        LIMIT :limit OFFSET :offset
        """
        
        # Execute main query
        applications = db_session.execute(text(query), params).fetchall()
        
        # Process applications
        app_list = []
        for app in applications:
            app_dict = {
                "id": app.id,
                "user_id": app.user_id,
                "payment_status": app.payment_status,
                "total_fee": app.total_fee,
                "status": app.status,
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "user_details": {
                    "id": app.user_id,
                    "email": app.email,
                    "first_name": app.first_name,
                    "last_name": app.last_name,
                    "phone": app.phone
                }
            }
            app_list.append(app_dict)
        
        # Create a default/unknown season for applications without details
        unknown_season = {
            "season_id": 0,
            "season_name": "Pending Applications",
            "applications": []
        }
        
        # Get application details (subjects and seasons) for each application
        seasons_dict = {}
        apps_with_details = set()
        
        for app in app_list:
            details_query = """
            SELECT 
                ad.id, ad.application_id, ad.season_id, ad.subject_id, ad.fee, ad.status,
                s.id as season_id, s.name as season_name,
                sub.id as subject_id, sub.name as subject_name
            FROM 
                application_details ad
            INNER JOIN 
                seasons s ON ad.season_id = s.id
            INNER JOIN 
                subjects sub ON ad.subject_id = sub.id
            WHERE 
                ad.application_id = :app_id
                AND ad.deleted_at IS NULL
            """
            
            details = db_session.execute(text(details_query), {"app_id": app["id"]}).fetchall()
            
            if details:
                # App has details - process normally
                apps_with_details.add(app["id"])
                
                # Group by season
                for detail in details:
                    season_id = detail.season_id
                    
                    # Initialize season if not exists
                    if season_id not in seasons_dict:
                        seasons_dict[season_id] = {
                            "season_id": season_id,
                            "season_name": detail.season_name,
                            "applications": []
                        }
                    
                    # Create subject object
                    subject = {
                        "id": detail.subject_id,
                        "name": detail.subject_name,
                        "fee": detail.fee,
                        "status": detail.status
                    }
                    
                    # Find or create application in this season
                    app_in_season = next((a for a in seasons_dict[season_id]["applications"] 
                                       if a["application_id"] == app["id"]), None)
                    
                    if app_in_season:
                        # Add subject to existing application
                        app_in_season["subjects"].append(subject)
                    else:
                        # Create new application entry for this season
                        seasons_dict[season_id]["applications"].append({
                            "application_id": app["id"],
                            "user_id": app["user_id"],
                            "total_fee": app["total_fee"],
                            "payment_status": app["payment_status"],
                            "status": app["status"],
                            "created_at": app["created_at"],
                            "user_details": app["user_details"],
                            "subjects": [subject]
                        })
            else:
                # App has no details - add to unknown season with default subject
                app_in_unknown = next((a for a in unknown_season["applications"] 
                                    if a["application_id"] == app["id"]), None)
                
                if not app_in_unknown:
                    # Create a default subject for display purposes
                    default_subject = {
                        "id": 0,
                        "name": "Unspecified Subject",
                        "fee": app["total_fee"],
                        "status": app["status"]
                    }
                    
                    # Add to unknown season
                    unknown_season["applications"].append({
                        "application_id": app["id"],
                        "user_id": app["user_id"],
                        "total_fee": app["total_fee"],
                        "payment_status": app["payment_status"],
                        "status": app["status"],
                        "created_at": app["created_at"],
                        "user_details": app["user_details"],
                        "subjects": [default_subject]
                    })
        
        # Convert to list for response and add unknown season if it has applications
        seasons_list = list(seasons_dict.values())
        if unknown_season["applications"]:
            seasons_list.append(unknown_season)
        
        return jsonify({
            "status": "success",
            "message": "User applications retrieved successfully",
            "data": {
                "seasons": seasons_list,
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
        print(f"ERROR in test_fixed_my_applications: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db_session.remove()