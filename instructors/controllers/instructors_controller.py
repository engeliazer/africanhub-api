from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import get_db
from instructors.models.models import Instructor
from instructors.models.schemas import InstructorCreate, InstructorUpdate, InstructorInDB
from instructors.controllers.photo_utils import handle_instructor_photo_upload
from datetime import datetime

instructors_bp = Blueprint('instructors', __name__)

@instructors_bp.route('/instructors', methods=['GET'])
@jwt_required()
def get_instructors():
    """Get all active instructors (admin only)"""
    try:
        db = get_db()
        instructors = db.query(Instructor).filter(
            Instructor.deleted_at.is_(None)
        ).order_by(Instructor.name.asc()).all()
        
        return jsonify({
            "status": "success",
            "data": [InstructorInDB.from_orm(instructor).dict() for instructor in instructors]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@instructors_bp.route('/instructors/<int:instructor_id>', methods=['GET'])
@jwt_required()
def get_instructor(instructor_id):
    """Get a specific instructor by ID"""
    try:
        db = get_db()
        instructor = db.query(Instructor).filter(
            Instructor.id == instructor_id,
            Instructor.deleted_at.is_(None)
        ).first()
        
        if not instructor:
            return jsonify({
                "status": "error",
                "message": "Instructor not found"
            }), 404
            
        return jsonify({
            "status": "success",
            "data": InstructorInDB.from_orm(instructor).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@instructors_bp.route('/instructors', methods=['POST'])
@jwt_required()
def create_instructor():
    """Create a new instructor with optional photo upload"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        # Handle form data (for file uploads) or JSON data
        if request.form:
            # Form data with file upload
            data = {
                'name': request.form.get('name'),
                'title': request.form.get('title'),
                'bio': request.form.get('bio'),
                'is_active': request.form.get('is_active', 'true').lower() == 'true'
            }
            
            # Handle photo upload
            photo_url = None
            if 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename != '':
                    photo_url = handle_instructor_photo_upload(photo_file, data['name'])
                    if not photo_url:
                        return jsonify({
                            "status": "error",
                            "message": "Invalid photo file. Only JPG, PNG, and GIF files are allowed."
                        }), 400
        else:
            # JSON data
            data = request.get_json()
            photo_url = data.get('photo')  # URL provided directly
        
        # Add created_by and updated_by
        data['created_by'] = current_user_id
        data['updated_by'] = current_user_id
        data['photo'] = photo_url
        
        instructor_data = InstructorCreate(**data)
        instructor = Instructor(**instructor_data.dict())
        db.add(instructor)
        db.commit()
        db.refresh(instructor)
        
        return jsonify({
            "status": "success",
            "data": InstructorInDB.from_orm(instructor).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@instructors_bp.route('/instructors/<int:instructor_id>', methods=['PUT'])
@jwt_required()
def update_instructor(instructor_id):
    """Update an instructor with optional photo upload"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        instructor = db.query(Instructor).filter(
            Instructor.id == instructor_id,
            Instructor.deleted_at.is_(None)
        ).first()
        
        if not instructor:
            return jsonify({
                "status": "error",
                "message": "Instructor not found"
            }), 404
        
        # Handle form data (for file uploads) or JSON data
        if request.form:
            # Form data with file upload
            data = {
                'name': request.form.get('name'),
                'title': request.form.get('title'),
                'bio': request.form.get('bio'),
                'is_active': request.form.get('is_active')
            }
            
            # Handle photo upload
            if 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename != '':
                    photo_url = handle_instructor_photo_upload(photo_file, data.get('name', instructor.name))
                    if not photo_url:
                        return jsonify({
                            "status": "error",
                            "message": "Invalid photo file. Only JPG, PNG, and GIF files are allowed."
                        }), 400
                    data['photo'] = photo_url
        else:
            # JSON data
            data = request.get_json()
        
        # Add updated_by
        data['updated_by'] = current_user_id
        
        update_data = InstructorUpdate(**data)
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(instructor, field, value)
            
        db.commit()
        db.refresh(instructor)
        
        return jsonify({
            "status": "success",
            "data": InstructorInDB.from_orm(instructor).dict()
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@instructors_bp.route('/instructors/<int:instructor_id>', methods=['DELETE'])
@jwt_required()
def delete_instructor(instructor_id):
    """Soft delete an instructor"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        instructor = db.query(Instructor).filter(
            Instructor.id == instructor_id,
            Instructor.deleted_at.is_(None)
        ).first()
        
        if not instructor:
            return jsonify({
                "status": "error",
                "message": "Instructor not found"
            }), 404
        
        # Soft delete
        instructor.deleted_at = datetime.utcnow()
        instructor.updated_by = current_user_id
        db.commit()
        
        return jsonify({
            "status": "success",
            "message": "Instructor deleted successfully"
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@instructors_bp.route('/instructors/public', methods=['GET'])
def get_instructors_public():
    """Public endpoint - Get all active instructors (no authentication required)"""
    try:
        db = get_db()
        instructors = db.query(Instructor).filter(
            Instructor.deleted_at.is_(None),
            Instructor.is_active == True
        ).order_by(Instructor.name.asc()).all()
        
        # Format response for public display
        instructors_data = []
        for instructor in instructors:
            instructor_dict = {
                "id": instructor.id,
                "name": instructor.name,
                "title": instructor.title,
                "bio": instructor.bio,
                "photo": instructor.photo
            }
            instructors_data.append(instructor_dict)
        
        return jsonify({
            "status": "success",
            "data": instructors_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()
