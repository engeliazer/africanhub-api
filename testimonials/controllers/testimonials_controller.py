from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import get_db
from certificates.models.models import Salutation
from testimonials.models.models import Testimonial
from testimonials.models.schemas import TestimonialCreate, TestimonialUpdate, TestimonialInDB, TestimonialReview, TestimonialPublic
from testimonials.controllers.photo_utils import handle_testimonial_photo_upload
from datetime import datetime

testimonials_bp = Blueprint('testimonials', __name__)


def _blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_id(value):
    if value in (None, ""):
        return None
    return int(value)


def _clean_person_fields(data):
    if "salutation_id" in data:
        data["salutation_id"] = _optional_id(data.get("salutation_id"))
    if "organization" in data:
        data["organization"] = _blank(data.get("organization"))
    return data


def _require_active_salutation(db, salutation_id):
    if salutation_id is None:
        return
    row = db.query(Salutation).filter(
        Salutation.id == salutation_id,
        Salutation.is_active.is_(True),
    ).first()
    if row is None:
        raise ValueError(f"Salutation {salutation_id} not found or inactive")


def _salutation_payload(salutation):
    if salutation is None:
        return None
    return {"id": salutation.id, "label": salutation.label, "code": salutation.code}


def _person_name(user):
    return f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()


def _attach_salutation(db, testimonial, payload):
    salutation = None
    if testimonial.salutation_id:
        salutation = db.query(Salutation).filter(Salutation.id == testimonial.salutation_id).first()
    payload["salutation"] = _salutation_payload(salutation)
    return payload


def _admin_payload(testimonial, user, salutation):
    payload = TestimonialInDB.from_orm(testimonial).dict()
    payload.update({
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "full_name": _person_name(user),
        "salutation": _salutation_payload(salutation),
    })
    return payload


def _testimonials_with_people(db):
    from auth.models.models import User

    return db.query(Testimonial, User, Salutation).join(
        User, Testimonial.user_id == User.id
    ).outerjoin(
        Salutation, Testimonial.salutation_id == Salutation.id
    )

@testimonials_bp.route('/testimonials', methods=['GET'])
@jwt_required()
def get_testimonials():
    """Get all testimonials (admin only) - includes pending and approved with user details"""
    try:
        db = get_db()
        testimonials = _testimonials_with_people(db).filter(
            Testimonial.deleted_at.is_(None)
        ).order_by(Testimonial.created_at.desc()).all()

        testimonials_data = [
            _admin_payload(testimonial, user, salutation)
            for testimonial, user, salutation in testimonials
        ]
        
        return jsonify({
            "status": "success",
            "data": testimonials_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@testimonials_bp.route('/testimonials/<int:testimonial_id>', methods=['GET'])
@jwt_required()
def get_testimonial(testimonial_id):
    """Get a specific testimonial by ID with user details"""
    try:
        db = get_db()
        result = _testimonials_with_people(db).filter(
            Testimonial.id == testimonial_id,
            Testimonial.deleted_at.is_(None)
        ).first()
        
        if not result:
            return jsonify({
                "status": "error",
                "message": "Testimonial not found"
            }), 404
        
        testimonial, user, salutation = result
        testimonial_dict = _admin_payload(testimonial, user, salutation)
            
        return jsonify({
            "status": "success",
            "data": testimonial_dict
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@testimonials_bp.route('/testimonials', methods=['POST'])
@jwt_required()
def create_testimonial():
    """Create a new testimonial with optional photo upload"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        # Handle form data (for file uploads) or JSON data
        if request.form:
            # Form data with file upload
            data = {
                'user_id': int(request.form.get('user_id')),
                'salutation_id': request.form.get('salutation_id'),
                'organization': request.form.get('organization'),
                'text': request.form.get('text'),
                'rating': int(request.form.get('rating', 5)),
                'is_active': request.form.get('is_active', 'true').lower() == 'true'
            }
            
            # Handle photo upload
            photo_url = None
            if 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename != '':
                    photo_url = handle_testimonial_photo_upload(photo_file, data['user_id'])
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
        data.pop('role', None)
        _clean_person_fields(data)
        _require_active_salutation(db, data.get('salutation_id'))
        
        testimonial_data = TestimonialCreate(**data)
        testimonial = Testimonial(**testimonial_data.dict())
        db.add(testimonial)
        db.commit()
        db.refresh(testimonial)
        
        payload = TestimonialInDB.from_orm(testimonial).dict()
        return jsonify({
            "status": "success",
            "data": _attach_salutation(db, testimonial, payload)
        }), 201
    except Exception as e:
        db.rollback()
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 400
    finally:
        db.close()

@testimonials_bp.route('/testimonials/<int:testimonial_id>', methods=['PUT'])
@jwt_required()
def update_testimonial(testimonial_id):
    """Update a testimonial with optional photo upload"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        testimonial = db.query(Testimonial).filter(
            Testimonial.id == testimonial_id,
            Testimonial.deleted_at.is_(None)
        ).first()
        
        if not testimonial:
            return jsonify({
                "status": "error",
                "message": "Testimonial not found"
            }), 404
        
        # Handle form data (for file uploads) or JSON data
        if request.form:
            # Form data with file upload
            data = {}
            
            # Only include fields that are present in the form data
            if 'salutation_id' in request.form:
                data['salutation_id'] = request.form.get('salutation_id')
            if 'organization' in request.form:
                data['organization'] = request.form.get('organization')
            if request.form.get('text') is not None:
                data['text'] = request.form.get('text')
            if request.form.get('rating') is not None:
                data['rating'] = int(request.form.get('rating'))
            if request.form.get('is_active') is not None:
                data['is_active'] = request.form.get('is_active').lower() == 'true'
            
            # Handle photo upload
            if 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename != '':
                    photo_url = handle_testimonial_photo_upload(photo_file, testimonial.user_id)
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
        data.pop('role', None)
        _clean_person_fields(data)
        if 'salutation_id' in data:
            _require_active_salutation(db, data.get('salutation_id'))
        
        update_data = TestimonialUpdate(**data)
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(testimonial, field, value)
            
        db.commit()
        db.refresh(testimonial)
        
        payload = TestimonialInDB.from_orm(testimonial).dict()
        return jsonify({
            "status": "success",
            "data": _attach_salutation(db, testimonial, payload)
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@testimonials_bp.route('/testimonials/<int:testimonial_id>', methods=['DELETE'])
@jwt_required()
def delete_testimonial(testimonial_id):
    """Soft delete a testimonial"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        testimonial = db.query(Testimonial).filter(
            Testimonial.id == testimonial_id,
            Testimonial.deleted_at.is_(None)
        ).first()
        
        if not testimonial:
            return jsonify({
                "status": "error",
                "message": "Testimonial not found"
            }), 404
        
        # Soft delete
        testimonial.deleted_at = datetime.utcnow()
        testimonial.updated_by = current_user_id
        db.commit()
        
        return jsonify({
            "status": "success",
            "message": "Testimonial deleted successfully"
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@testimonials_bp.route('/testimonials/public', methods=['GET'])
def get_testimonials_public():
    """Public endpoint - Get all approved testimonials (no authentication required)"""
    try:
        db = get_db()
        testimonials = _testimonials_with_people(db).filter(
            Testimonial.deleted_at.is_(None),
            Testimonial.is_active == True,
            Testimonial.is_approved == True  # Only approved testimonials
        ).order_by(Testimonial.created_at.desc()).all()
        
        testimonials_data = []
        for testimonial, user, salutation in testimonials:
            testimonials_data.append({
                "id": testimonial.id,
                "name": _person_name(user),
                "salutation_id": testimonial.salutation_id,
                "salutation": salutation.label if salutation else None,
                "organization": testimonial.organization,
                "text": testimonial.text,
                "photo": testimonial.photo,
                "rating": testimonial.rating,
            })
        
        return jsonify({
            "status": "success",
            "data": testimonials_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@testimonials_bp.route('/testimonials/pending', methods=['GET'])
@jwt_required()
def get_pending_testimonials():
    """Get all pending testimonials (admin only) with user details"""
    try:
        db = get_db()
        testimonials = _testimonials_with_people(db).filter(
            Testimonial.deleted_at.is_(None),
            Testimonial.is_approved == False
        ).order_by(Testimonial.created_at.asc()).all()

        testimonials_data = [
            _admin_payload(testimonial, user, salutation)
            for testimonial, user, salutation in testimonials
        ]
        
        return jsonify({
            "status": "success",
            "data": testimonials_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@testimonials_bp.route('/testimonials/<int:testimonial_id>/review', methods=['PUT'])
@jwt_required()
def review_testimonial(testimonial_id):
    """Review a testimonial (approve/reject) - admin only"""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        
        testimonial = db.query(Testimonial).filter(
            Testimonial.id == testimonial_id,
            Testimonial.deleted_at.is_(None)
        ).first()
        
        if not testimonial:
            return jsonify({
                "status": "error",
                "message": "Testimonial not found"
            }), 404
        
        data = request.get_json()
        review_data = TestimonialReview(**data)
        
        # Update testimonial with review
        testimonial.is_approved = review_data.is_approved
        testimonial.reviewed_by = review_data.reviewed_by
        testimonial.reviewed_at = datetime.utcnow()
        testimonial.updated_by = review_data.updated_by
        
        db.commit()
        db.refresh(testimonial)
        
        payload = TestimonialInDB.from_orm(testimonial).dict()
        return jsonify({
            "status": "success",
            "data": _attach_salutation(db, testimonial, payload)
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()
