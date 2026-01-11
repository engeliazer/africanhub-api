from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

from subjects.models.models import SubTopic, Topic
from subjects.models.schemas import SubTopicCreate, SubTopicUpdate, SubTopicInDB
from database.db_connector import db_session

subtopic_bp = Blueprint('subtopic', __name__)

class SubTopicsController:
    def __init__(self, db: Session):
        self.db = db

    def create_subtopic(self, subtopic: SubTopicCreate) -> SubTopicInDB:
        """Create a new subtopic"""
        try:
            # Check if topic exists
            topic = self.db.query(Topic).filter(
                Topic.id == subtopic.topic_id,
                Topic.deleted_at.is_(None)
            ).first()
            if not topic:
                raise NotFound("Topic not found")

            db_subtopic = SubTopic(
                topic_id=subtopic.topic_id,
                name=subtopic.name,
                code=subtopic.code,
                description=subtopic.description,
                is_active=subtopic.is_active,
                created_by=subtopic.created_by,
                updated_by=subtopic.updated_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_subtopic)
            self.db.commit()
            self.db.refresh(db_subtopic)
            return SubTopicInDB.from_orm(db_subtopic)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("SubTopic code already exists for this topic")

    def get_subtopic(self, subtopic_id: int) -> Optional[SubTopicInDB]:
        """Get a subtopic by ID"""
        subtopic = self.db.query(SubTopic).filter(
            SubTopic.id == subtopic_id,
            SubTopic.deleted_at.is_(None)
        ).first()
        if not subtopic:
            raise NotFound("SubTopic not found")
        return SubTopicInDB.from_orm(subtopic)

    def get_subtopics(self, skip: int = 0, limit: int = 100, topic_id: Optional[int] = None) -> List[SubTopicInDB]:
        """Get all subtopics with pagination and optional topic filter"""
        query = self.db.query(SubTopic).filter(SubTopic.deleted_at.is_(None))
        
        if topic_id:
            query = query.filter(SubTopic.topic_id == topic_id)
        
        subtopics = query.offset(skip).limit(limit).all()
        return [SubTopicInDB.from_orm(subtopic) for subtopic in subtopics]

    def update_subtopic(self, subtopic_id: int, subtopic_update: SubTopicUpdate) -> SubTopicInDB:
        """Update a subtopic"""
        db_subtopic = self.db.query(SubTopic).filter(
            SubTopic.id == subtopic_id,
            SubTopic.deleted_at.is_(None)
        ).first()
        if not db_subtopic:
            raise NotFound("SubTopic not found")

        update_data = subtopic_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_subtopic, field, value)

        db_subtopic.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(db_subtopic)
            return SubTopicInDB.from_orm(db_subtopic)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("SubTopic code already exists for this topic")

    def delete_subtopic(self, subtopic_id: int) -> bool:
        """Soft delete a subtopic"""
        db_subtopic = self.db.query(SubTopic).filter(
            SubTopic.id == subtopic_id,
            SubTopic.deleted_at.is_(None)
        ).first()
        if not db_subtopic:
            raise NotFound("SubTopic not found")

        db_subtopic.deleted_at = datetime.utcnow()
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise BadRequest("Could not delete subtopic")

# API Routes
@subtopic_bp.route('/api/subtopics', methods=['POST'])
@jwt_required()
def create_subtopic():
    """Create a new subtopic"""
    try:
        data = request.get_json()
        subtopic_data = SubTopicCreate(**data)
        controller = SubTopicsController(db_session)
        subtopic = controller.create_subtopic(subtopic_data)
        return jsonify({
            "status": "success",
            "message": "SubTopic created successfully",
            "data": subtopic.dict()
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@subtopic_bp.route('/api/subtopics', methods=['GET'])
@jwt_required()
def get_subtopics():
    """Get all subtopics"""
    try:
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        topic_id = request.args.get('topic_id', None, type=int)
        
        controller = SubTopicsController(db_session)
        subtopics = controller.get_subtopics(skip, limit, topic_id)
        return jsonify({
            "status": "success",
            "message": "SubTopics retrieved successfully",
            "data": {
                "subtopics": [subtopic.dict() for subtopic in subtopics]
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@subtopic_bp.route('/api/subtopics/<int:subtopic_id>', methods=['GET'])
@jwt_required()
def get_subtopic(subtopic_id):
    """Get a specific subtopic"""
    try:
        controller = SubTopicsController(db_session)
        subtopic = controller.get_subtopic(subtopic_id)
        return jsonify({
            "status": "success",
            "message": "SubTopic retrieved successfully",
            "data": subtopic.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404

@subtopic_bp.route('/api/subtopics/<int:subtopic_id>', methods=['PUT'])
@jwt_required()
def update_subtopic(subtopic_id):
    """Update a subtopic"""
    try:
        data = request.get_json()
        subtopic_data = SubTopicUpdate(**data)
        controller = SubTopicsController(db_session)
        subtopic = controller.update_subtopic(subtopic_id, subtopic_data)
        return jsonify({
            "status": "success",
            "message": "SubTopic updated successfully",
            "data": subtopic.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@subtopic_bp.route('/api/subtopics/<int:subtopic_id>', methods=['DELETE'])
@jwt_required()
def delete_subtopic(subtopic_id):
    """Delete a subtopic"""
    try:
        controller = SubTopicsController(db_session)
        success = controller.delete_subtopic(subtopic_id)
        return jsonify({
            "status": "success",
            "message": "SubTopic deleted successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404 