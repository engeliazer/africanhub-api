from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import get_db
from auth.models.models import User
from applications.models.models import Application, ApplicationDetail, ApplicationStatus
from subjects.models.models import Season, Subject, Topic, SubTopic, SeasonSubject, SeasonApplicant
from subjects.models.schemas import (
    SeasonCreate, SeasonUpdate, SeasonInDB,
    SubjectCreate, SubjectUpdate, SubjectInDB,
    TopicCreate, TopicUpdate, TopicInDB,
    SubTopicCreate, SubTopicUpdate, SubTopicInDB,
    SeasonSubjectCreate, SeasonSubjectUpdate, SeasonSubjectInDB,
    SeasonApplicantCreate, SeasonApplicantUpdate, SeasonApplicantInDB
)
from studies.models.models import SubtopicMaterial
from sqlalchemy import and_, func
from auth.middleware.token_middleware import token_refresh_middleware
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import os
import re
import shutil
import logging

logger = logging.getLogger(__name__)

# Create blueprints for each subject-related entity
seasons_bp = Blueprint('seasons', __name__)
subjects_bp = Blueprint('subjects', __name__)
topics_bp = Blueprint('topics', __name__)
subtopics_bp = Blueprint('subtopics', __name__)
season_subjects_bp = Blueprint('season_subjects', __name__)
season_applicants_bp = Blueprint('season_applicants', __name__)

# Token refresh hooks removed; no backend-managed timeouts

# Season routes
@seasons_bp.route('/seasons', methods=['GET'])
@jwt_required()
def get_seasons():
    try:
        db = get_db()
        seasons = db.query(Season).all()
        return jsonify({
            "status": "success",
            "data": [SeasonInDB.from_orm(season).dict() for season in seasons]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@seasons_bp.route('/seasons/<int:season_id>', methods=['GET'])
@jwt_required()
def get_season(season_id):
    try:
        db = get_db()
        season = db.query(Season).filter(Season.id == season_id).first()
        if not season:
            return jsonify({
                "status": "error",
                "message": "Season not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": SeasonInDB.from_orm(season).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@seasons_bp.route('/seasons', methods=['POST'])
@jwt_required()
def create_season():
    try:
        db = get_db()
        data = request.get_json()
        season_data = SeasonCreate(**data)
        season = Season(**season_data.dict())
        db.add(season)
        db.commit()
        db.refresh(season)
        return jsonify({
            "status": "success",
            "data": SeasonInDB.from_orm(season).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@seasons_bp.route('/season-pending-subjects/<int:season_id>', methods=['GET'])
@jwt_required()
def get_season_pending_subjects(season_id):
    """Get all active subjects that are not added to the specified season"""
    try:
        db = get_db()
        
        # First verify that the season exists
        season = db.query(Season)\
            .filter(
                and_(
                    Season.id == season_id,
                    Season.is_active == True
                )
            ).first()
        
        if not season:
            return jsonify({
                "status": "error",
                "message": "Season not found"
            }), 404

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Subquery to get all subject IDs that are already in season_subjects
        existing_subject_ids = db.query(SeasonSubject.subject_id)\
            .filter(
                SeasonSubject.season_id == season_id,
                SeasonSubject.is_active == True
            )
        
        # Main query to get subjects that are not in the subquery
        query = db.query(Subject)\
            .filter(
                Subject.is_active == True,
                ~Subject.id.in_(existing_subject_ids)
            )
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        subjects = query.order_by(Subject.name)\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            "status": "success",
            "message": "Pending subjects retrieved successfully",
            "data": {
                "subjects": [SubjectInDB.from_orm(subject).dict() for subject in subjects],
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

@seasons_bp.route('/seasons/available-seasons', methods=['GET'])
@jwt_required()
def get_available_seasons():
    """Get all seasons that have subjects the user hasn't applied for"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        db = get_db()
        
        # Get all seasons that are active and have subjects
        seasons_with_subjects = db.query(Season).join(
            SeasonSubject
        ).filter(
            and_(
                Season.is_active == True,
                SeasonSubject.is_active == True
            )
        ).distinct().all()

        # Get all seasons the user has already applied for (excluding withdrawn applications)
        applied_seasons = db.query(ApplicationDetail.season_id)\
            .join(Application, ApplicationDetail.application_id == Application.id)\
            .filter(
                and_(
                    Application.user_id == current_user_id,
                    Application.is_active == True,
                    ApplicationDetail.is_active == True,
                    Application.status != ApplicationStatus.withdrawn.value  # Exclude withdrawn applications
                )
            ).distinct().all()
        applied_season_ids = [season[0] for season in applied_seasons]

        # Filter out seasons the user has already applied for
        available_seasons = [
            season for season in seasons_with_subjects 
            if season.id not in applied_season_ids
        ]

        return jsonify({
            "status": "success",
            "data": [SeasonInDB.from_orm(season).dict() for season in available_seasons]
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@seasons_bp.route('/seasons/<int:season_id>/available-subjects', methods=['GET'])
@jwt_required()
def get_season_available_subjects(season_id):
    """Get all subjects that haven't been added to the specified season"""
    try:
        db = get_db()
        
        # First verify that the season exists and is active
        season = db.query(Season).filter(
            and_(
                Season.id == season_id,
                Season.is_active == True
            )
        ).first()
        
        if not season:
            return jsonify({
                "status": "error",
                "message": "Season not found or inactive"
            }), 404

        # Get all subject IDs that are already in season_subjects for this season
        existing_subject_ids = db.query(SeasonSubject.subject_id)\
            .filter(
                SeasonSubject.season_id == season_id,
                SeasonSubject.is_active == True
            )

        # Get all active subjects that are not in the season_subjects
        subjects = db.query(Subject)\
            .filter(
                and_(
                    Subject.is_active == True,
                    ~Subject.id.in_(existing_subject_ids)
                )
            ).all()

        return jsonify({
            "status": "success",
            "message": "Available subjects retrieved successfully",
            "data": {
                "season": {
                    "id": season.id,
                    "name": season.name,
                    "code": season.code,
                    "start_date": season.start_date.strftime("%Y-%m-%d"),
                    "end_date": season.end_date.strftime("%Y-%m-%d"),
                    "description": season.description,
                    "is_active": season.is_active
                },
                "subjects": [SubjectInDB.from_orm(subject).dict() for subject in subjects]
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@seasons_bp.route('/seasons/<int:season_id>/user-available-subjects', methods=['GET'])
@jwt_required()
def get_user_available_subjects(season_id):
    """Get all subjects under a season that the user hasn't applied for"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        db = get_db()
        
        # First verify that the season exists and is active
        season = db.query(Season).filter(
            and_(
                Season.id == season_id,
                Season.is_active == True
            )
        ).first()
        
        if not season:
            return jsonify({
                "status": "error",
                "message": "Season not found or inactive"
            }), 404

        # Get all subjects that are active in this season
        subjects_in_season = db.query(Subject)\
            .join(SeasonSubject, Subject.id == SeasonSubject.subject_id)\
            .filter(
                and_(
                    SeasonSubject.season_id == season_id,
                    SeasonSubject.is_active == True,
                    Subject.is_active == True
                )
            ).distinct().all()

        # Get all subjects the user has already applied for in this season (excluding withdrawn applications)
        applied_subjects = db.query(ApplicationDetail.subject_id)\
            .join(Application, ApplicationDetail.application_id == Application.id)\
            .filter(
                and_(
                    Application.user_id == current_user_id,
                    ApplicationDetail.season_id == season_id,
                    Application.is_active == True,
                    ApplicationDetail.is_active == True,
                    Application.status != ApplicationStatus.withdrawn.value  # Exclude withdrawn applications
                )
            ).distinct().all()
        applied_subject_ids = [subject[0] for subject in applied_subjects]

        # Filter out subjects the user has already applied for
        available_subjects = [
            SubjectInDB.from_orm(subject).dict() 
            for subject in subjects_in_season 
            if subject.id not in applied_subject_ids
        ]

        return jsonify({
            "status": "success",
            "data": available_subjects
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@seasons_bp.route('/seasons/<int:season_id>/available-subjects-list', methods=['GET'])
@jwt_required()
def get_available_subjects(season_id):
    """Get all subjects under a season that the user hasn't applied for"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        db = get_db()
        
        # First verify that the season exists and is active
        season = db.query(Season).filter(
            and_(
                Season.id == season_id,
                Season.is_active == True
            )
        ).first()
        
        if not season:
            return jsonify({
                "status": "error",
                "message": "Season not found or inactive"
            }), 404

        # Get all subjects that are active in this season
        available_subjects = db.query(
            Subject.id,
            Subject.name,
            Subject.current_price,
            func.count(ApplicationDetail.id).label('enrolled')
        ).join(
            SeasonSubject, Subject.id == SeasonSubject.subject_id
        ).outerjoin(
            ApplicationDetail,
            and_(
                ApplicationDetail.subject_id == Subject.id,
                ApplicationDetail.season_id == season_id,
                ApplicationDetail.is_active == True
            )
        ).filter(
            and_(
                SeasonSubject.season_id == season_id,
                SeasonSubject.is_active == True,
                Subject.is_active == True
            )
        ).group_by(
            Subject.id,
            Subject.name,
            Subject.current_price
        ).all()

        # Get all subjects the user has already applied for in this season (excluding withdrawn applications)
        applied_subjects = db.query(ApplicationDetail.subject_id)\
            .join(Application, ApplicationDetail.application_id == Application.id)\
            .filter(
                and_(
                    Application.user_id == current_user_id,
                    ApplicationDetail.season_id == season_id,
                    Application.is_active == True,
                    ApplicationDetail.is_active == True,
                    Application.status != ApplicationStatus.withdrawn.value  # Exclude withdrawn applications
                )
            ).distinct().all()
        applied_subject_ids = [subject[0] for subject in applied_subjects]

        # Get all subjects the user has already applied for in this season (excluding withdrawn applications)
        applied_subjects = db.query(ApplicationDetail.subject_id)\
            .join(Application, ApplicationDetail.application_id == Application.id)\
            .filter(
                and_(
                    Application.user_id == current_user_id,
                    ApplicationDetail.season_id == season_id,
                    Application.is_active == True,
                    ApplicationDetail.is_active == True,
                    Application.status != ApplicationStatus.withdrawn.value
                )
            ).distinct().all()
        applied_subject_ids = [subject[0] for subject in applied_subjects]

        # Format the response
        subjects_data = []
        for subject in available_subjects:
            if subject.id not in applied_subject_ids:
                subjects_data.append({
                    "id": subject.id,
                    "subject_id": subject.id,
                    "name": subject.name,
                    "price": subject.current_price,
                    "capacity": 0,  # Default to 0 since capacity is not tracked
                    "enrolled": subject.enrolled
                })

        return jsonify({
            "status": "success",
            "data": subjects_data
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

# Subject routes
@subjects_bp.route('/subjects', methods=['GET'])
@jwt_required()
def get_subjects():
    try:
        db = get_db()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', type=int)  # No default - return all if not specified
        
        # If no per_page specified, return all subjects
        if per_page is None:
            per_page = 1000  # Large number to get all subjects
            page = 1  # Reset to first page when getting all
        
        offset = (page - 1) * per_page
        
        # Build query excluding deleted records
        query = db.query(Subject).filter(Subject.deleted_at.is_(None))
        
        # Get total count for pagination
        total_count = query.count()
        
        # Get paginated subjects
        subjects = query.order_by(Subject.created_at.desc())\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        # Prepare response data
        response_data = {
            "subjects": [SubjectInDB.from_orm(subject).dict() for subject in subjects]
        }
        
        # Only include pagination info if per_page was specified
        if request.args.get('per_page') is not None:
            response_data["pagination"] = {
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        else:
            response_data["total"] = total_count
            response_data["message"] = "All subjects returned (no pagination)"
        
        return jsonify({
            "status": "success",
            "data": response_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subjects_bp.route('/subjects/<int:subject_id>', methods=['GET'])
@jwt_required()
def get_subject(subject_id):
    try:
        db = get_db()
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            return jsonify({
                "status": "error",
                "message": "Subject not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": SubjectInDB.from_orm(subject).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subjects_bp.route('/subjects', methods=['POST'])
@jwt_required()
def create_subject():
    try:
        db = get_db()
        data = request.get_json()
        subject_data = SubjectCreate(**data)
        subject = Subject(**subject_data.dict())
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return jsonify({
            "status": "success",
            "data": SubjectInDB.from_orm(subject).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subjects_bp.route('/subjects/with-topic-subtopic', methods=['POST'])
@jwt_required()
def create_subject_with_topic_subtopic():
    """Create a new subject with associated topic and subtopic"""
    try:
        db = get_db()
        data = request.get_json()
        
        # Validate subject data
        subject_data = SubjectCreate(**data['subject'])
        
        # Start transaction
        try:
            # Create subject
            db_subject = Subject(
                name=subject_data.name,
                code=subject_data.code,
                description=subject_data.description,
                current_price=subject_data.current_price,
                is_active=subject_data.is_active,
                created_by=subject_data.created_by,
                updated_by=subject_data.updated_by
            )
            db.add(db_subject)
            db.flush()  # Flush to get subject ID
            
            # Create topic with subject_id
            topic_data = TopicCreate(**{
                **data['topic'],
                'subject_id': db_subject.id,  # Set the subject_id after subject creation
                'created_by': subject_data.created_by,
                'updated_by': subject_data.updated_by
            })
            db_topic = Topic(
                subject_id=topic_data.subject_id,
                name=topic_data.name,
                code=topic_data.code,
                description=topic_data.description,
                is_active=topic_data.is_active,
                created_by=topic_data.created_by,
                updated_by=topic_data.updated_by
            )
            db.add(db_topic)
            db.flush()  # Flush to get topic ID
            
            # Create subtopic with topic_id
            subtopic_data = SubTopicCreate(**{
                **data['subtopic'],
                'topic_id': db_topic.id,  # Set the topic_id after topic creation
                'created_by': subject_data.created_by,
                'updated_by': subject_data.updated_by
            })
            db_subtopic = SubTopic(
                topic_id=subtopic_data.topic_id,
                name=subtopic_data.name,
                code=subtopic_data.code,
                description=subtopic_data.description,
                is_active=subtopic_data.is_active,
                created_by=subtopic_data.created_by,
                updated_by=subtopic_data.updated_by
            )
            db.add(db_subtopic)
            
            # Commit the transaction
            db.commit()
            
            # Refresh all objects to get their complete data
            db.refresh(db_subject)
            db.refresh(db_topic)
            db.refresh(db_subtopic)
            
            return jsonify({
                "status": "success",
                "message": "Subject with topic and subtopic created successfully",
                "data": {
                    "subject": SubjectInDB.from_orm(db_subject).dict(),
                    "topic": TopicInDB.from_orm(db_topic).dict(),
                    "subtopic": SubTopicInDB.from_orm(db_subtopic).dict()
                }
            }), 201
            
        except IntegrityError as e:
            db.rollback()
            error_message = str(e)
            if "subjects.code" in error_message:
                return jsonify({
                    "status": "error",
                    "message": "A subject with this code already exists"
                }), 400
            elif "topics.code" in error_message:
                return jsonify({
                    "status": "error",
                    "message": "A topic with this code already exists"
                }), 400
            elif "sub_topics.code" in error_message:
                return jsonify({
                    "status": "error",
                    "message": "A subtopic with this code already exists"
                }), 400
            else:
                return jsonify({
                    "status": "error",
                    "message": "One of the codes (subject, topic, or subtopic) already exists"
                }), 400
            
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@subjects_bp.route('/subjects/<int:subject_id>', methods=['PUT'])
@jwt_required()
def update_subject(subject_id):
    """Update a specific subject"""
    try:
        db = get_db()
        subject = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.is_active == True
        ).first()
        
        if not subject:
            return jsonify({
                "status": "error",
                "message": "Subject not found"
            }), 404
        
        data = request.get_json()
        subject_data = SubjectUpdate(**data)
        
        update_data = subject_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(subject, field, value)
        
        db.commit()
        db.refresh(subject)
        
        return jsonify({
            "status": "success",
            "message": "Subject updated successfully",
            "data": SubjectInDB.from_orm(subject).dict()
        }), 200
        
    except IntegrityError:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": "Subject code already exists"
        }), 400
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subjects_bp.route('/subjects/<int:subject_id>', methods=['DELETE'])
@jwt_required()
def delete_subject(subject_id):
    """Delete a subject by ID"""
    try:
        db = get_db()
        subject = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.deleted_at.is_(None)
        ).first()
        
        if not subject:
            return jsonify({
                "status": "error",
                "message": "Subject not found"
            }), 404
            
        # Soft delete by setting deleted_at
        subject.deleted_at = func.current_timestamp()
        db.commit()
        
        return jsonify({
            "status": "success",
            "message": "Subject deleted successfully"
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

# Topic routes
@topics_bp.route('/topics', methods=['GET'])
@jwt_required()
def get_topics():
    try:
        db = get_db()
        
        # Get query parameters
        subject_id = request.args.get('subject_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build query
        query = db.query(Topic)
        
        # Apply subject filter if provided
        if subject_id:
            query = query.filter(Topic.subject_id == subject_id)
        
        # Get total count
        total_count = query.count()
        
        # Get paginated topics
        topics = query.order_by(Topic.name)\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            "status": "success",
            "data": {
                "topics": [TopicInDB.from_orm(topic).dict() for topic in topics],
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

@topics_bp.route('/topics/<int:topic_id>', methods=['GET'])
@jwt_required()
def get_topic(topic_id):
    try:
        db = get_db()
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return jsonify({
                "status": "error",
                "message": "Topic not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": TopicInDB.from_orm(topic).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@topics_bp.route('/topics/<int:topic_id>', methods=['PUT'])
@jwt_required()
def update_topic(topic_id):
    """Update a specific topic"""
    try:
        db = get_db()
        topic = db.query(Topic).filter(
            Topic.id == topic_id,
            Topic.is_active == True
        ).first()
        
        if not topic:
            return jsonify({
                "status": "error",
                "message": "Topic not found"
            }), 404
        
        data = request.get_json()
        topic_data = TopicUpdate(**data)
        
        update_data = topic_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(topic, field, value)
        
        db.commit()
        db.refresh(topic)
        
        return jsonify({
            "status": "success",
            "message": "Topic updated successfully",
            "data": TopicInDB.from_orm(topic).dict()
        }), 200
        
    except IntegrityError:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": "A topic with this code already exists"
        }), 400
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@topics_bp.route('/topics/<int:topic_id>', methods=['DELETE'])
@jwt_required()
def delete_topic(topic_id):
    """Soft delete a topic by setting is_active to False"""
    try:
        db = get_db()
        topic = db.query(Topic).filter(
            Topic.id == topic_id,
            Topic.is_active == True
        ).first()
        
        if not topic:
            return jsonify({
                "status": "error",
                "message": "Topic not found or already deleted"
            }), 404
        
        # Soft delete by setting is_active to False
        topic.is_active = False
        db.commit()
        
        return jsonify({
            "status": "success",
            "message": "Topic deleted successfully"
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@topics_bp.route('/topics', methods=['POST'])
@jwt_required()
def create_topic():
    """Create a new topic with optional associated subtopic"""
    try:
        db = get_db()
        data = request.get_json()
        
        # Check if this is nested format (topic + subtopic) or flat format (topic only)
        if 'topic' in data and 'subtopic' in data:
            # Nested format - create topic with subtopic
            topic_data = TopicCreate(**data['topic'])
            
            # Verify that the subject exists
            subject = db.query(Subject).filter(
                Subject.id == topic_data.subject_id,
                Subject.deleted_at.is_(None)
            ).first()
            
            if not subject:
                return jsonify({
                    "status": "error",
                    "message": "Subject not found"
                }), 404
            
            # Create topic
            db_topic = Topic(
                subject_id=topic_data.subject_id,
                name=topic_data.name,
                code=topic_data.code,
                description=topic_data.description,
                is_active=topic_data.is_active,
                created_by=topic_data.created_by,
                updated_by=topic_data.updated_by
            )
            db.add(db_topic)
            db.flush()  # Flush to get topic ID
            
            # Create subtopic with topic_id
            subtopic_data = SubTopicCreate(**{
                **data['subtopic'],
                'topic_id': db_topic.id,  # Set the topic_id after topic creation
                'created_by': topic_data.created_by,
                'updated_by': topic_data.updated_by
            })
            db_subtopic = SubTopic(
                topic_id=subtopic_data.topic_id,
                name=subtopic_data.name,
                code=subtopic_data.code,
                description=subtopic_data.description,
                is_active=subtopic_data.is_active,
                created_by=subtopic_data.created_by,
                updated_by=subtopic_data.updated_by
            )
            db.add(db_subtopic)
            
            # Commit the transaction
            db.commit()
            
            # Refresh all objects to get their complete data
            db.refresh(db_topic)
            db.refresh(db_subtopic)
            
            return jsonify({
                "status": "success",
                "message": "Topic with subtopic created successfully",
                "data": {
                    "topic": TopicInDB.from_orm(db_topic).dict(),
                    "subtopic": SubTopicInDB.from_orm(db_subtopic).dict()
                }
            }), 201
        else:
            # Flat format - create topic only
            topic_data = TopicCreate(**data)
            topic = Topic(**topic_data.dict())
            db.add(topic)
            db.commit()
            db.refresh(topic)
            return jsonify({
                "status": "success",
                "data": TopicInDB.from_orm(topic).dict()
            }), 201
            
    except IntegrityError as e:
        db.rollback()
        error_message = str(e)
        if "topics.code" in error_message or "Duplicate entry" in error_message:
            return jsonify({
                "status": "error",
                "message": "A topic with this code already exists"
            }), 400
        elif "sub_topics.code" in error_message:
            return jsonify({
                "status": "error",
                "message": "A subtopic with this code already exists"
            }), 400
        else:
            return jsonify({
                "status": "error",
                "message": "Database integrity error"
            }), 400
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

# SubTopic routes
@subtopics_bp.route('/subtopics', methods=['GET'])
@jwt_required()
def get_subtopics():
    try:
        db = get_db()
        
        # Get query parameters
        topic_id = request.args.get('topic_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build query
        query = db.query(SubTopic)
        
        # Apply topic filter if provided
        if topic_id:
            query = query.filter(SubTopic.topic_id == topic_id)
        
        # Get total count
        total_count = query.count()
        
        # Get paginated subtopics
        subtopics = query.order_by(SubTopic.name)\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            "status": "success",
            "data": {
                "subtopics": [SubTopicInDB.from_orm(subtopic).dict() for subtopic in subtopics],
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

@subtopics_bp.route('/subtopics/<int:subtopic_id>', methods=['GET'])
@jwt_required()
def get_subtopic(subtopic_id):
    try:
        db = get_db()
        subtopic = db.query(SubTopic).filter(SubTopic.id == subtopic_id).first()
        if not subtopic:
            return jsonify({
                "status": "error",
                "message": "SubTopic not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": SubTopicInDB.from_orm(subtopic).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subtopics_bp.route('/subtopics/<int:subtopic_id>', methods=['PUT'])
@jwt_required()
def update_subtopic(subtopic_id):
    """Update a specific subtopic"""
    try:
        db = get_db()
        subtopic = db.query(SubTopic).filter(
            SubTopic.id == subtopic_id
        ).first()
        
        if not subtopic:
            return jsonify({
                "status": "error",
                "message": "SubTopic not found"
            }), 404
        
        data = request.get_json()
        subtopic_data = SubTopicUpdate(**data)
        
        update_data = subtopic_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(subtopic, field, value)
        
        db.commit()
        db.refresh(subtopic)
        
        return jsonify({
            "status": "success",
            "message": "SubTopic updated successfully",
            "data": SubTopicInDB.from_orm(subtopic).dict()
        }), 200
        
    except IntegrityError:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": "A subtopic with this code already exists"
        }), 400
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subtopics_bp.route('/subtopics/<int:subtopic_id>', methods=['DELETE'])
@jwt_required()
def delete_subtopic(subtopic_id):
    """Permanently delete a subtopic and all related materials"""
    try:
        db = get_db()
        subtopic = db.query(SubTopic).filter(
            SubTopic.id == subtopic_id
        ).first()
        
        if not subtopic:
            return jsonify({
                "status": "error",
                "message": "SubTopic not found"
            }), 404
        
        # Get all materials for this subtopic
        materials = db.query(SubtopicMaterial).filter(
            SubtopicMaterial.subtopic_id == subtopic_id
        ).all()
        
        # Import here to avoid circular imports
        from config import UPLOAD_FOLDER
        
        # Clean up each material's external resources before deletion
        for material in materials:
            try:
                # Delete VdoCipher video if this is a DRM-protected video
                if material.vdocipher_video_id and material.requires_drm:
                    try:
                        from services.vdocipher_service import VdoCipherService
                        vdocipher = VdoCipherService()
                        vdocipher.delete_video(material.vdocipher_video_id)
                        logger.info(f"✅ Deleted VdoCipher video {material.vdocipher_video_id} for material {material.id}")
                    except Exception as vdo_err:
                        logger.warning(f"Failed to delete VdoCipher video {material.vdocipher_video_id}: {vdo_err}")
                        # Continue with cleanup even if VdoCipher deletion fails
                
                # Clean up filesystem files
                try:
                    path_value = (material.material_path or '').replace('\\', '/')
                    storage_location = getattr(material, 'storage_location', 'local')
                    
                    # Helper: safely remove a file or directory tree if it exists
                    def safe_remove(path_to_remove):
                        try:
                            if os.path.isdir(path_to_remove):
                                shutil.rmtree(path_to_remove, ignore_errors=True)
                            elif os.path.isfile(path_to_remove):
                                os.remove(path_to_remove)
                        except Exception as _fs_err:
                            logger.warning(f"Failed to remove path {path_to_remove}: {_fs_err}")
                    
                    # If this material produced local HLS, remove its folder
                    if storage_location == 'local' and path_value.endswith('output.m3u8'):
                        try:
                            manifest_abs = path_value
                            if not manifest_abs.startswith('storage/'):
                                manifest_abs = os.path.join(UPLOAD_FOLDER, path_value)
                            # Parent directory that contains manifest and segments
                            hls_dir = os.path.dirname(manifest_abs)
                            # Extra safety: ensure we're inside uploads/hls
                            if os.path.abspath(hls_dir).startswith(os.path.abspath(os.path.join(UPLOAD_FOLDER, 'hls'))):
                                safe_remove(hls_dir)
                        except Exception as _hls_err:
                            logger.warning(f"Error removing HLS folder for material {material.id}: {_hls_err}")
                    
                    # If a temp upload directory exists for this material, remove it as well
                    try:
                        m = re.search(r"temp/([a-f0-9\-]{36})/", path_value, re.IGNORECASE)
                        if m:
                            uuid_part = m.group(1)
                            temp_dir = os.path.join(UPLOAD_FOLDER, 'temp', uuid_part)
                            if os.path.abspath(temp_dir).startswith(os.path.abspath(os.path.join(UPLOAD_FOLDER, 'temp'))):
                                safe_remove(temp_dir)
                    except Exception as _tmp_err:
                        logger.warning(f"Error removing temp folder for material {material.id}: {_tmp_err}")
                except Exception as _cleanup_err:
                    logger.warning(f"Cleanup error for material {material.id}: {_cleanup_err}")
                    
            except Exception as material_cleanup_err:
                logger.warning(f"Error cleaning up material {material.id}: {material_cleanup_err}")
                # Continue with other materials even if one fails
        
        # Permanently delete the subtopic (cascade will delete materials at DB level)
        db.delete(subtopic)
        db.commit()
        
        logger.info(f"✅ Permanently deleted subtopic {subtopic_id} and {len(materials)} related materials")
        
        return jsonify({
            "status": "success",
            "message": f"SubTopic and {len(materials)} related materials deleted successfully"
        }), 200
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting subtopic {subtopic_id}: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@subtopics_bp.route('/subtopics', methods=['POST'])
@jwt_required()
def create_subtopic():
    try:
        db = get_db()
        data = request.get_json()
        subtopic_data = SubTopicCreate(**data)
        subtopic = SubTopic(**subtopic_data.dict())
        db.add(subtopic)
        db.commit()
        db.refresh(subtopic)
        return jsonify({
            "status": "success",
            "data": SubTopicInDB.from_orm(subtopic).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

# SeasonSubject routes
@season_subjects_bp.route('/season-subjects', methods=['GET'])
@jwt_required()
def get_season_subjects():
    try:
        db = get_db()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build query
        query = db.query(SeasonSubject).filter(SeasonSubject.is_active == True)
        
        # Get total count
        total_count = query.count()
        
        # Get paginated season subjects
        season_subjects = query.order_by(SeasonSubject.created_at.desc())\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            "status": "success",
            "data": {
                "season_subjects": [SeasonSubjectInDB.from_orm(ss).dict() for ss in season_subjects],
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

@season_subjects_bp.route('/season-subjects/<int:season_subject_id>', methods=['GET'])
@jwt_required()
def get_season_subject(season_subject_id):
    try:
        db = get_db()
        season_subject = db.query(SeasonSubject).filter(SeasonSubject.id == season_subject_id).first()
        if not season_subject:
            return jsonify({
                "status": "error",
                "message": "SeasonSubject not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": SeasonSubjectInDB.from_orm(season_subject).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@season_subjects_bp.route('/season-subjects', methods=['POST'])
@jwt_required()
def create_season_subject():
    try:
        db = get_db()
        data = request.get_json()
        season_subject_data = SeasonSubjectCreate(**data)
        season_subject = SeasonSubject(**season_subject_data.dict())
        db.add(season_subject)
        db.commit()
        db.refresh(season_subject)
        return jsonify({
            "status": "success",
            "data": SeasonSubjectInDB.from_orm(season_subject).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@season_subjects_bp.route('/season-subjects/season/<int:season_id>', methods=['GET'])
@jwt_required()
def get_season_subjects_by_season(season_id):
    try:
        db = get_db()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build query
        query = db.query(SeasonSubject).filter(
            and_(
                SeasonSubject.season_id == season_id,
                SeasonSubject.is_active == True
            )
        )
        
        # Get total count
        total_count = query.count()
        
        # Get paginated season subjects
        season_subjects = query.order_by(SeasonSubject.created_at)\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            "status": "success",
            "data": {
                "season_subjects": [SeasonSubjectInDB.from_orm(ss).dict() for ss in season_subjects],
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

@season_subjects_bp.route('/season-subjects/<int:season_subject_id>/delete', methods=['DELETE'])
@jwt_required()
def delete_season_subject(season_subject_id):
    """Soft delete a season subject"""
    try:
        db = get_db()
        
        # Find the season subject
        season_subject = db.query(SeasonSubject)\
            .filter(
                and_(
                    SeasonSubject.id == season_subject_id,
                    SeasonSubject.is_active == True
                )
            ).first()
        
        if not season_subject:
            return jsonify({
                "status": "error",
                "message": "Season subject not found"
            }), 404
        
        # Soft delete by setting is_active to False
        season_subject.is_active = False
        db.commit()
        
        return jsonify({
            "status": "success",
            "message": "Season subject deleted successfully"
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

# SeasonApplicant routes
@season_applicants_bp.route('/season-applicants', methods=['GET'])
@jwt_required()
def get_all_season_applicants():
    try:
        db = get_db()
        season_applicants = db.query(SeasonApplicant).all()
        return jsonify({
            "status": "success",
            "data": [SeasonApplicantInDB.from_orm(sa).dict() for sa in season_applicants]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@season_applicants_bp.route('/season-applicants/<int:season_applicant_id>', methods=['GET'])
@jwt_required()
def get_season_applicant(season_applicant_id):
    try:
        db = get_db()
        season_applicant = db.query(SeasonApplicant).filter(SeasonApplicant.id == season_applicant_id).first()
        if not season_applicant:
            return jsonify({
                "status": "error",
                "message": "SeasonApplicant not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": SeasonApplicantInDB.from_orm(season_applicant).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@season_applicants_bp.route('/season-applicants', methods=['POST'])
@jwt_required()
def create_season_applicant():
    try:
        db = get_db()
        data = request.get_json()
        season_applicant_data = SeasonApplicantCreate(**data)
        season_applicant = SeasonApplicant(**season_applicant_data.dict())
        db.add(season_applicant)
        db.commit()
        db.refresh(season_applicant)
        return jsonify({
            "status": "success",
            "data": SeasonApplicantInDB.from_orm(season_applicant).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@season_applicants_bp.route('/season-applicants/season/<int:season_id>', methods=['GET'])
@jwt_required()
def get_season_applicants(season_id):
    """Get all applicants for a specific season with pagination"""
    try:
        db = get_db()
        
        # Get season information
        season = db.query(Season).filter(Season.id == season_id).first()
        if not season:
            return jsonify({
                "status": "error",
                "message": "Season not found"
            }), 404

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        offset = (page - 1) * per_page

        # Get applications for the season with user details
        query = db.query(Application, ApplicationDetail, User, Subject)\
            .join(ApplicationDetail, Application.id == ApplicationDetail.application_id)\
            .join(User, Application.user_id == User.id)\
            .join(Subject, ApplicationDetail.subject_id == Subject.id)\
            .filter(ApplicationDetail.season_id == season_id)\
            .filter(Application.is_active == True)\
            .filter(ApplicationDetail.is_active == True)

        # Count total records
        total = query.count()

        # Get paginated results
        results = query.order_by(Application.created_at.desc())\
            .offset(offset)\
            .limit(per_page)\
            .all()

        # Get all subjects for the season through season_subjects
        season_subjects = db.query(SeasonSubject, Subject)\
            .join(Subject, SeasonSubject.subject_id == Subject.id)\
            .filter(SeasonSubject.season_id == season_id)\
            .filter(SeasonSubject.is_active == True)\
            .filter(Subject.is_active == True)\
            .order_by(Subject.name)\
            .all()

        # Prepare response data
        applications_data = []
        for app, detail, user, subject in results:
            applications_data.append({
                "id": app.id,
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone": user.phone
                },
                "application_detail": {
                    "id": detail.id,
                    "subject": {
                        "id": subject.id,
                        "name": subject.name,
                        "code": subject.code
                    },
                    "fee": detail.fee,
                    "status": detail.status.value
                },
                "application": {
                    "status": app.status.value,
                    "payment_status": app.payment_status.value,
                    "total_fee": app.total_fee,
                    "created_at": app.created_at.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "updated_at": app.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
                }
            })

        subjects_data = [
            {
                "id": ss.id,
                "subject": {
                    "id": s.id,
                    "name": s.name,
                    "code": s.code
                },
                "created_at": ss.created_at.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "updated_at": ss.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
            }
            for ss, s in season_subjects
        ]

        return jsonify({
            "status": "success",
            "data": {
                "season": {
                    "id": season.id,
                    "name": season.name,
                    "code": season.code,
                    "start_date": season.start_date.strftime("%Y-%m-%d"),
                    "end_date": season.end_date.strftime("%Y-%m-%d"),
                    "description": season.description,
                    "is_active": season.is_active
                },
                "applications": applications_data,
                "subjects": subjects_data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page
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

@season_applicants_bp.route('/user-applications/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_applications(user_id):
    """Get all applications for a specific user across all seasons"""
    try:
        db = get_db()
        
        # Get user information
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 404

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        offset = (page - 1) * per_page

        # Get applications for the user with all related details
        query = db.query(Application, ApplicationDetail, Season, Subject)\
            .join(ApplicationDetail, Application.id == ApplicationDetail.application_id)\
            .join(Season, ApplicationDetail.season_id == Season.id)\
            .join(Subject, ApplicationDetail.subject_id == Subject.id)\
            .filter(Application.user_id == user_id)\
            .filter(Application.is_active == True)\
            .filter(ApplicationDetail.is_active == True)

        # Count total records
        total = query.count()

        # Get paginated results
        results = query.order_by(Application.created_at.desc())\
            .offset(offset)\
            .limit(per_page)\
            .all()

        # Prepare response data
        applications_data = []
        for app, detail, season, subject in results:
            applications_data.append({
                "id": app.id,
                "season": {
                    "id": season.id,
                    "name": season.name,
                    "code": season.code,
                    "start_date": season.start_date.strftime("%Y-%m-%d"),
                    "end_date": season.end_date.strftime("%Y-%m-%d"),
                    "description": season.description,
                    "is_active": season.is_active
                },
                "application_detail": {
                    "id": detail.id,
                    "subject": {
                        "id": subject.id,
                        "name": subject.name,
                        "code": subject.code
                    },
                    "fee": detail.fee,
                    "status": detail.status.value
                },
                "application": {
                    "status": app.status.value,
                    "payment_status": app.payment_status.value,
                    "total_fee": app.total_fee,
                    "created_at": app.created_at.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "updated_at": app.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
                }
            })

        return jsonify({
            "status": "success",
            "data": {
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone": user.phone
                },
                "applications": applications_data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page
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

@seasons_bp.route('/schedules/public', methods=['GET'])
def get_schedules_public():
    """Public endpoint - Get all active seasons with their subjects (no authentication required)"""
    try:
        db = get_db()
        from datetime import date
        
        # Get active seasons (current and future)
        today = date.today()
        seasons = db.query(Season).filter(
            Season.is_active == True,
            Season.end_date >= today  # Include current and future seasons
        ).order_by(Season.start_date.asc()).all()
        
        # Build response with subjects for each season
        seasons_data = []
        for season in seasons:
            # Get active subjects for this season through season_subjects
            season_subjects = db.query(SeasonSubject).filter(
                SeasonSubject.season_id == season.id,
                SeasonSubject.is_active == True
            ).all()
            
            # Get the actual subject details
            subjects_data = []
            for season_subject in season_subjects:
                subject = db.query(Subject).filter(
                    Subject.id == season_subject.subject_id,
                    Subject.deleted_at.is_(None),
                    Subject.is_active == True
                ).first()
                
                if subject:
                    subject_dict = {
                        "id": subject.id,
                        "name": subject.name,
                        "code": subject.code,
                        "description": subject.description,
                        "current_price": subject.current_price
                    }
                    subjects_data.append(subject_dict)
            
            season_dict = {
                "id": season.id,
                "name": season.name,
                "code": season.code,
                "start_date": season.start_date.isoformat() if season.start_date else None,
                "end_date": season.end_date.isoformat() if season.end_date else None,
                "description": season.description,
                "is_active": season.is_active,
                "subjects": subjects_data
            }
            seasons_data.append(season_dict)
        
        return jsonify({
            "status": "success",
            "data": seasons_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()
