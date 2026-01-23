from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

from subjects.models.models import Subject
from subjects.models.schemas import SubjectCreate, SubjectUpdate, SubjectInDB
from database.db_connector import db_session

subject_bp = Blueprint('subject', __name__)

class SubjectsController:
    def __init__(self, db: Session):
        self.db = db

    def create_subject(self, subject: SubjectCreate) -> SubjectInDB:
        """Create a new subject"""
        try:
            db_subject = Subject(
                name=subject.name,
                code=subject.code,
                description=subject.description,
                current_price=subject.current_price,
                duration_days=subject.duration_days,
                trial_duration_days=subject.trial_duration_days,
                is_active=subject.is_active,
                created_by=subject.created_by,
                updated_by=subject.updated_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_subject)
            self.db.commit()
            self.db.refresh(db_subject)
            return SubjectInDB.from_orm(db_subject)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Subject code already exists")

    def get_subject(self, subject_id: int) -> Optional[SubjectInDB]:
        """Get a subject by ID"""
        subject = self.db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.deleted_at.is_(None)
        ).first()
        if not subject:
            raise NotFound("Subject not found")
        return SubjectInDB.from_orm(subject)

    def get_subjects(self, skip: int = 0, limit: int = 100) -> List[SubjectInDB]:
        """Get all subjects with pagination"""
        subjects = self.db.query(Subject).filter(
            Subject.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()
        return [SubjectInDB.from_orm(subject) for subject in subjects]

    def update_subject(self, subject_id: int, subject_update: SubjectUpdate) -> SubjectInDB:
        """Update a subject"""
        db_subject = self.db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.deleted_at.is_(None)
        ).first()
        if not db_subject:
            raise NotFound("Subject not found")

        update_data = subject_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_subject, field, value)

        db_subject.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(db_subject)
            return SubjectInDB.from_orm(db_subject)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Subject code already exists")

    def delete_subject(self, subject_id: int) -> bool:
        """Soft delete a subject"""
        db_subject = self.db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.deleted_at.is_(None)
        ).first()
        if not db_subject:
            raise NotFound("Subject not found")

        db_subject.deleted_at = datetime.utcnow()
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise BadRequest("Could not delete subject")

# API Routes
@subject_bp.route('/api/subjects', methods=['POST'])
@jwt_required()
def create_subject():
    """Create a new subject"""
    try:
        data = request.get_json()
        subject_data = SubjectCreate(**data)
        controller = SubjectsController(db_session)
        subject = controller.create_subject(subject_data)
        return jsonify({
            "status": "success",
            "message": "Subject created successfully",
            "data": subject.dict()
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@subject_bp.route('/api/subjects', methods=['GET'])
@jwt_required()
def get_subjects():
    """Get all subjects"""
    try:
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        controller = SubjectsController(db_session)
        subjects = controller.get_subjects(skip, limit)
        return jsonify({
            "status": "success",
            "message": "Subjects retrieved successfully",
            "data": {
                "subjects": [subject.dict() for subject in subjects]
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@subject_bp.route('/api/subjects/<int:subject_id>', methods=['GET'])
@jwt_required()
def get_subject(subject_id):
    """Get a specific subject"""
    try:
        controller = SubjectsController(db_session)
        subject = controller.get_subject(subject_id)
        return jsonify({
            "status": "success",
            "message": "Subject retrieved successfully",
            "data": subject.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404

@subject_bp.route('/api/subjects/<int:subject_id>', methods=['PUT'])
@jwt_required()
def update_subject(subject_id):
    """Update a subject"""
    try:
        data = request.get_json()
        subject_data = SubjectUpdate(**data)
        controller = SubjectsController(db_session)
        subject = controller.update_subject(subject_id, subject_data)
        return jsonify({
            "status": "success",
            "message": "Subject updated successfully",
            "data": subject.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@subject_bp.route('/api/subjects/<int:subject_id>', methods=['DELETE'])
@jwt_required()
def delete_subject(subject_id):
    """Delete a subject"""
    try:
        controller = SubjectsController(db_session)
        success = controller.delete_subject(subject_id)
        return jsonify({
            "status": "success",
            "message": "Subject deleted successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404 