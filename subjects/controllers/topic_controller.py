from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

from subjects.models.models import Topic, Subject
from subjects.models.schemas import TopicCreate, TopicUpdate, TopicInDB
from database.db_connector import db_session

topic_bp = Blueprint('topic', __name__)

class TopicsController:
    def __init__(self, db: Session):
        self.db = db

    def create_topic(self, topic: TopicCreate) -> TopicInDB:
        """Create a new topic"""
        try:
            # Check if subject exists
            subject = self.db.query(Subject).filter(
                Subject.id == topic.subject_id,
                Subject.deleted_at.is_(None)
            ).first()
            if not subject:
                raise NotFound("Subject not found")

            db_topic = Topic(
                subject_id=topic.subject_id,
                name=topic.name,
                code=topic.code,
                description=topic.description,
                is_active=topic.is_active,
                created_by=topic.created_by,
                updated_by=topic.updated_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_topic)
            self.db.commit()
            self.db.refresh(db_topic)
            return TopicInDB.from_orm(db_topic)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Topic code already exists for this subject")

    def get_topic(self, topic_id: int) -> Optional[TopicInDB]:
        """Get a topic by ID"""
        topic = self.db.query(Topic).filter(
            Topic.id == topic_id,
            Topic.deleted_at.is_(None)
        ).first()
        if not topic:
            raise NotFound("Topic not found")
        return TopicInDB.from_orm(topic)

    def get_topics(self, skip: int = 0, limit: int = 100, subject_id: Optional[int] = None) -> List[TopicInDB]:
        """Get all topics with pagination and optional subject filter"""
        query = self.db.query(Topic).filter(Topic.deleted_at.is_(None))
        
        if subject_id:
            query = query.filter(Topic.subject_id == subject_id)
        
        topics = query.offset(skip).limit(limit).all()
        return [TopicInDB.from_orm(topic) for topic in topics]

    def update_topic(self, topic_id: int, topic_update: TopicUpdate) -> TopicInDB:
        """Update a topic"""
        db_topic = self.db.query(Topic).filter(
            Topic.id == topic_id,
            Topic.deleted_at.is_(None)
        ).first()
        if not db_topic:
            raise NotFound("Topic not found")

        update_data = topic_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_topic, field, value)

        db_topic.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(db_topic)
            return TopicInDB.from_orm(db_topic)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Topic code already exists for this subject")

    def delete_topic(self, topic_id: int) -> bool:
        """Soft delete a topic"""
        db_topic = self.db.query(Topic).filter(
            Topic.id == topic_id,
            Topic.deleted_at.is_(None)
        ).first()
        if not db_topic:
            raise NotFound("Topic not found")

        db_topic.deleted_at = datetime.utcnow()
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise BadRequest("Could not delete topic")

# API Routes
@topic_bp.route('/api/topics', methods=['POST'])
@jwt_required()
def create_topic():
    """Create a new topic"""
    try:
        data = request.get_json()
        topic_data = TopicCreate(**data)
        controller = TopicsController(db_session)
        topic = controller.create_topic(topic_data)
        return jsonify({
            "status": "success",
            "message": "Topic created successfully",
            "data": topic.dict()
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@topic_bp.route('/api/topics', methods=['GET'])
@jwt_required()
def get_topics():
    """Get all topics"""
    try:
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        subject_id = request.args.get('subject_id', None, type=int)
        
        controller = TopicsController(db_session)
        topics = controller.get_topics(skip, limit, subject_id)
        return jsonify({
            "status": "success",
            "message": "Topics retrieved successfully",
            "data": {
                "topics": [topic.dict() for topic in topics]
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@topic_bp.route('/api/topics/<int:topic_id>', methods=['GET'])
@jwt_required()
def get_topic(topic_id):
    """Get a specific topic"""
    try:
        controller = TopicsController(db_session)
        topic = controller.get_topic(topic_id)
        return jsonify({
            "status": "success",
            "message": "Topic retrieved successfully",
            "data": topic.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404

@topic_bp.route('/api/topics/<int:topic_id>', methods=['PUT'])
@jwt_required()
def update_topic(topic_id):
    """Update a topic"""
    try:
        data = request.get_json()
        topic_data = TopicUpdate(**data)
        controller = TopicsController(db_session)
        topic = controller.update_topic(topic_id, topic_data)
        return jsonify({
            "status": "success",
            "message": "Topic updated successfully",
            "data": topic.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@topic_bp.route('/api/topics/<int:topic_id>', methods=['DELETE'])
@jwt_required()
def delete_topic(topic_id):
    """Delete a topic"""
    try:
        controller = TopicsController(db_session)
        success = controller.delete_topic(topic_id)
        return jsonify({
            "status": "success",
            "message": "Topic deleted successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404 