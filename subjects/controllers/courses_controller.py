from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import text
from datetime import datetime
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import db_session
from subjects.models.models import Subject, Topic, SubTopic, Course, CourseSubject
from studies.models.models import SubtopicMaterial, StudyMaterialCategory

courses_bp = Blueprint('courses', __name__)

# Course CRUD routes removed - courses component eliminated
# Only keeping refactored endpoints that work with subjects directly


@courses_bp.route('/api/courses/public', methods=['GET'])
def get_courses_public():
    """Public catalog: courses with nested subjects (matches DCRC/cloned system format). No auth required."""
    try:
        courses = db_session.query(Course).filter(
            Course.is_active == True,
            Course.deleted_at.is_(None),
        ).order_by(Course.id).all()

        result = []
        for c in courses:
            subjects = (
                db_session.query(Subject)
                .join(CourseSubject, CourseSubject.subject_id == Subject.id)
                .filter(
                    CourseSubject.course_id == c.id,
                    CourseSubject.is_active == True,
                    Subject.is_active == True,
                    Subject.deleted_at.is_(None),
                )
                .order_by(Subject.name)
                .all()
            )

            subjects_data = []
            for s in subjects:
                subject_dict = {
                    "id": s.id,
                    "name": s.name,
                    "code": s.code,
                    "description": s.description,
                    "current_price": s.current_price,
                    "course_id": c.id,
                    "course": {
                        "id": c.id,
                        "name": c.name,
                        "code": c.code,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                        "created_by": c.created_by,
                        "updated_by": c.updated_by,
                        "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None,
                        "is_active": c.is_active,
                        "description": c.description,
                    },
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "created_by": s.created_by,
                    "updated_by": s.updated_by,
                    "deleted_at": s.deleted_at.isoformat() if s.deleted_at else None,
                    "deleted_by": None,
                }
                subjects_data.append(subject_dict)

            course_dict = {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "description": c.description,
                "is_active": c.is_active,
                "created_by": c.created_by,
                "updated_by": c.updated_by,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None,
                "subjects": subjects_data,
            }
            result.append(course_dict)

        return jsonify({
            "status": "success",
            "message": "Public courses retrieved successfully",
            "data": result,
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_courses_public: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@courses_bp.route('/api/courses/approved', methods=['GET'])
@jwt_required()
def get_approved_courses():
    try:
        # Get the current user's ID from the JWT token
        current_user_id = get_jwt_identity()
        
        # Query to get approved applications with their subjects
        query = text("""
            SELECT DISTINCT 
                s.id as subject_id,
                s.name as subject_name,
                s.code as subject_code,
                s.description as subject_description,
                t.id as topic_id,
                t.name as topic_name,
                t.code as topic_code,
                t.description as topic_description,
                st.id as subtopic_id,
                st.name as subtopic_name,
                st.code as subtopic_code,
                st.description as subtopic_description,
                sm.id as material_id,
                sm.name as material_name,
                sm.material_path,
                sm.extension_type,
                sm.video_duration,
                sm.file_size,
                sm.material_category_id,
                smc.id as category_id,
                smc.name as category_name,
                smc.code as category_code,
                smc.description as category_description,
                smc.is_protected
            FROM applications a
            JOIN application_details ad ON a.id = ad.application_id
            JOIN subjects s ON ad.subject_id = s.id
            JOIN topics t ON s.id = t.subject_id
            JOIN sub_topics st ON t.id = st.topic_id
            LEFT JOIN subtopic_materials sm ON st.id = sm.subtopic_id
            LEFT JOIN study_material_categories smc ON sm.material_category_id = smc.id
            WHERE a.user_id = :user_id
            AND a.status = 'approved'
            AND a.is_active = true
            AND ad.is_active = true
            AND s.is_active = true
            AND t.is_active = true
            AND st.is_active = true
            ORDER BY s.name, t.name, st.name, smc.name, sm.name
        """)
        
        result = db_session.execute(query, {"user_id": current_user_id})
        
        # Process the results into a structured format
        subjects = {}
        for row in result:
            subject_id = row.subject_id
            if subject_id not in subjects:
                subjects[subject_id] = {
                    "id": subject_id,
                    "name": row.subject_name,
                    "code": row.subject_code,
                    "description": row.subject_description,
                    "topics": {}
                }
            
            topic_id = row.topic_id
            if topic_id not in subjects[subject_id]["topics"]:
                subjects[subject_id]["topics"][topic_id] = {
                    "id": topic_id,
                    "name": row.topic_name,
                    "code": row.topic_code,
                    "description": row.topic_description,
                    "subtopics": {}
                }
            
            subtopic_id = row.subtopic_id
            if subtopic_id not in subjects[subject_id]["topics"][topic_id]["subtopics"]:
                subjects[subject_id]["topics"][topic_id]["subtopics"][subtopic_id] = {
                    "id": subtopic_id,
                    "name": row.subtopic_name,
                    "code": row.subtopic_code,
                    "description": row.subtopic_description,
                    "materials": {}
                }
            
            # Add material information if available
            if row.material_id:
                category_id = row.category_id
                if category_id not in subjects[subject_id]["topics"][topic_id]["subtopics"][subtopic_id]["materials"]:
                    subjects[subject_id]["topics"][topic_id]["subtopics"][subtopic_id]["materials"][category_id] = {
                        "id": category_id,
                        "name": row.category_name,
                        "code": row.category_code,
                        "description": row.category_description,
                        "is_protected": bool(row.is_protected),
                        "material_category_id": row.material_category_id,
                        "files": []
                    }
                
                # Add file information
                subjects[subject_id]["topics"][topic_id]["subtopics"][subtopic_id]["materials"][category_id]["files"].append({
                    "id": row.material_id,
                    "name": row.material_name,
                    "path": row.material_path,
                    "extension_type": row.extension_type,
                    "video_duration": row.video_duration,
                    "file_size": row.file_size,
                    "material_category_id": row.material_category_id
                })
        
        # Convert dictionaries to lists for JSON serialization
        for subject_id in subjects:
            subjects[subject_id]["topics"] = list(subjects[subject_id]["topics"].values())
            for topic in subjects[subject_id]["topics"]:
                topic["subtopics"] = list(topic["subtopics"].values())
                for subtopic in topic["subtopics"]:
                    subtopic["materials"] = list(subtopic["materials"].values())
        
        return jsonify({
            "status": "success",
            "message": "Approved subjects retrieved successfully",
            "data": {
                "subjects": list(subjects.values())
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_approved_courses: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@courses_bp.route('/api/subject-structure', methods=['GET'])
@jwt_required()
def get_subject_structure():
    """Get complete subject structure including subjects, topics, and subtopics"""
    try:
        # Get optional filter parameters
        subject_id = request.args.get('subject_id', type=int)
        topic_id = request.args.get('topic_id', type=int)
        nested = request.args.get('nested', 'false').lower() == 'true'
        
        # Base queries
        subjects_query = db_session.query(Subject).filter(Subject.is_active == True, Subject.deleted_at.is_(None))
        topics_query = db_session.query(Topic).filter(Topic.is_active == True)
        subtopics_query = db_session.query(SubTopic).filter(SubTopic.is_active == True)
        
        # Apply filters if provided
        if subject_id:
            subjects_query = subjects_query.filter(Subject.id == subject_id)
            topics_query = topics_query.filter(Topic.subject_id == subject_id)
            subtopics_query = subtopics_query.join(Topic, SubTopic.topic_id == Topic.id).filter(Topic.subject_id == subject_id)
        
        if topic_id:
            topics_query = topics_query.filter(Topic.id == topic_id)
            subtopics_query = subtopics_query.filter(SubTopic.topic_id == topic_id)
        
        # Execute queries
        subjects = subjects_query.all()
        topics = topics_query.all()
        subtopics = subtopics_query.all()
        
        if nested:
            # Create a dictionary to store topics by subject
            topics_dict = {}
            for topic in topics:
                if topic.subject_id not in topics_dict:
                    topics_dict[topic.subject_id] = []
                topics_dict[topic.subject_id].append({
                    "id": str(topic.id),
                    "subject_id": str(topic.subject_id),
                    "name": topic.name,
                    "code": topic.code,
                    "description": topic.description,
                    "order": None,  # Not present in current model
                    "duration": None,  # Not present in current model
                    "created_at": topic.created_at.isoformat() if topic.created_at else None,
                    "updated_at": topic.updated_at.isoformat() if topic.updated_at else None,
                    "subtopics": []
                })
            
            # Create a dictionary to store subtopics by topic
            subtopics_dict = {}
            for subtopic in subtopics:
                if subtopic.topic_id not in subtopics_dict:
                    subtopics_dict[subtopic.topic_id] = []
                subtopics_dict[subtopic.topic_id].append({
                    "id": str(subtopic.id),
                    "topic_id": str(subtopic.topic_id),
                    "name": subtopic.name,
                    "code": subtopic.code,
                    "description": subtopic.description,
                    "order": None,  # Not present in current model
                    "duration": None,  # Not present in current model
                    "created_at": subtopic.created_at.isoformat() if subtopic.created_at else None,
                    "updated_at": subtopic.updated_at.isoformat() if subtopic.updated_at else None
                })
            
            # Build nested structure
            nested_subjects = []
            for subject in subjects:
                subject_data = {
                    "id": str(subject.id),
                    "name": subject.name,
                    "code": subject.code,
                    "description": subject.description,
                    "price": subject.current_price,
                    "credits": None,  # Not present in current model
                    "status": "active" if subject.is_active else "inactive",
                    "created_at": subject.created_at.isoformat() if subject.created_at else None,
                    "updated_at": subject.updated_at.isoformat() if subject.updated_at else None,
                    "topics": []
                }
                
                # Add topics with subtopics
                for topic in topics_dict.get(subject.id, []):
                    topic["subtopics"] = subtopics_dict.get(int(topic["id"]), [])
                    subject_data["topics"].append(topic)
                
                nested_subjects.append(subject_data)
            
            response = {
                "subjects": nested_subjects
            }
        else:
            response = {
                "subjects": [
                    {
                        "id": str(subject.id),
                        "name": subject.name,
                        "code": subject.code,
                        "description": subject.description,
                        "price": subject.current_price,
                        "credits": None,  # Not present in current model
                        "status": "active" if subject.is_active else "inactive",
                        "created_at": subject.created_at.isoformat() if subject.created_at else None,
                        "updated_at": subject.updated_at.isoformat() if subject.updated_at else None
                    }
                    for subject in subjects
                ],
                "topics": [
                    {
                        "id": str(topic.id),
                        "subject_id": str(topic.subject_id),
                        "name": topic.name,
                        "description": topic.description,
                        "order": None,  # Not present in current model
                        "duration": None,  # Not present in current model
                        "created_at": topic.created_at.isoformat() if topic.created_at else None,
                        "updated_at": topic.updated_at.isoformat() if topic.updated_at else None
                    }
                    for topic in topics
                ],
                "subtopics": [
                    {
                        "id": str(subtopic.id),
                        "topic_id": str(subtopic.topic_id),
                        "name": subtopic.name,
                        "description": subtopic.description,
                        "order": None,  # Not present in current model
                        "duration": None,  # Not present in current model
                        "created_at": subtopic.created_at.isoformat() if subtopic.created_at else None,
                        "updated_at": subtopic.updated_at.isoformat() if subtopic.updated_at else None
                    }
                    for subtopic in subtopics
                ]
            }
        
        return jsonify({
            "status": "success",
            "message": "Subject structure retrieved successfully",
            "data": response
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500 