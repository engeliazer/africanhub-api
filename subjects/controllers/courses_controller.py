from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import text
from datetime import datetime
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import db_session
from subjects.models.models import Course, Subject, Topic, SubTopic
from subjects.models.schemas import CourseCreate, CourseUpdate
from studies.models.models import SubtopicMaterial, StudyMaterialCategory

courses_bp = Blueprint('courses', __name__)

@courses_bp.route('/api/courses', methods=['POST'])
@jwt_required()
def create_course():
    try:
        # Get the current user ID from the JWT token
        current_user_id = get_jwt_identity()
        
        # Get the request data
        data = request.get_json()
        
        # Add the created_by and updated_by fields
        data['created_by'] = int(current_user_id)
        data['updated_by'] = int(current_user_id)
        
        # Create the course
        course_data = CourseCreate(**data)
        db_course = Course(**course_data.dict())
        db_session.add(db_course)
        db_session.commit()
        db_session.refresh(db_course)
        return jsonify(course_data.dict()), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@courses_bp.route('/api/courses', methods=['GET'])
@jwt_required()
def get_courses():
    try:
        courses = db_session.query(Course).filter(Course.deleted_at.is_(None)).all()
        return jsonify([{
            "id": course.id,
            "name": course.name,
            "code": course.code,
            "description": course.description,
            "is_active": course.is_active,
            "created_at": course.created_at.isoformat() if course.created_at else None,
            "updated_at": course.updated_at.isoformat() if course.updated_at else None
        } for course in courses])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@courses_bp.route('/api/courses/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course(course_id):
    try:
        course = db_session.query(Course).filter(
            Course.id == course_id,
            Course.deleted_at.is_(None)
        ).first()
        if not course:
            return jsonify({"error": "Course not found"}), 404
        return jsonify({
            "id": course.id,
            "name": course.name,
            "code": course.code,
            "description": course.description,
            "is_active": course.is_active,
            "created_at": course.created_at.isoformat() if course.created_at else None,
            "updated_at": course.updated_at.isoformat() if course.updated_at else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@courses_bp.route('/api/courses/<int:course_id>', methods=['PUT'])
@jwt_required()
def update_course(course_id):
    try:
        # Get the current user ID from the JWT token
        current_user_id = get_jwt_identity()
        
        # Get the request data
        data = request.get_json()
        
        # Add the updated_by field
        data['updated_by'] = int(current_user_id)
        
        # Update the course
        course_data = CourseUpdate(**data)
        course = db_session.query(Course).filter(
            Course.id == course_id,
            Course.deleted_at.is_(None)
        ).first()
        if not course:
            return jsonify({"error": "Course not found"}), 404
            
        for field, value in course_data.dict(exclude_unset=True).items():
            setattr(course, field, value)
            
        db_session.commit()
        db_session.refresh(course)
        return jsonify({
            "id": course.id,
            "name": course.name,
            "code": course.code,
            "description": course.description,
            "is_active": course.is_active,
            "created_at": course.created_at.isoformat() if course.created_at else None,
            "updated_at": course.updated_at.isoformat() if course.updated_at else None
        })
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@courses_bp.route('/api/courses/<int:course_id>', methods=['DELETE'])
@jwt_required()
def delete_course(course_id):
    try:
        current_user_id = get_jwt_identity()
        course = db_session.query(Course).filter(
            Course.id == course_id,
            Course.deleted_at.is_(None)
        ).first()
        if not course:
            return jsonify({"error": "Course not found"}), 404
            
        # Soft delete
        course.deleted_at = datetime.utcnow()
        course.updated_by = current_user_id
        db_session.commit()
        return jsonify({"message": "Course deleted successfully"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@courses_bp.route('/api/courses/approved', methods=['GET'])
@jwt_required()
def get_approved_courses():
    try:
        # Get the current user's ID from the JWT token
        current_user_id = get_jwt_identity()
        
        # Query to get approved applications with their subjects and courses
        query = text("""
            SELECT DISTINCT 
                c.id as course_id,
                c.name as course_name,
                c.code as course_code,
                c.description as course_description,
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
            JOIN courses c ON s.course_id = c.id
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
            ORDER BY c.name, s.name, t.name, st.name, smc.name, sm.name
        """)
        
        result = db_session.execute(query, {"user_id": current_user_id})
        
        # Process the results into a structured format
        courses = {}
        for row in result:
            course_id = row.course_id
            if course_id not in courses:
                courses[course_id] = {
                    "id": course_id,
                    "name": row.course_name,
                    "code": row.course_code,
                    "description": row.course_description,
                    "subjects": {}
                }
            
            subject_id = row.subject_id
            if subject_id not in courses[course_id]["subjects"]:
                courses[course_id]["subjects"][subject_id] = {
                    "id": subject_id,
                    "name": row.subject_name,
                    "code": row.subject_code,
                    "description": row.subject_description,
                    "topics": {}
                }
            
            topic_id = row.topic_id
            if topic_id not in courses[course_id]["subjects"][subject_id]["topics"]:
                courses[course_id]["subjects"][subject_id]["topics"][topic_id] = {
                    "id": topic_id,
                    "name": row.topic_name,
                    "code": row.topic_code,
                    "description": row.topic_description,
                    "subtopics": {}
                }
            
            subtopic_id = row.subtopic_id
            if subtopic_id not in courses[course_id]["subjects"][subject_id]["topics"][topic_id]["subtopics"]:
                courses[course_id]["subjects"][subject_id]["topics"][topic_id]["subtopics"][subtopic_id] = {
                    "id": subtopic_id,
                    "name": row.subtopic_name,
                    "code": row.subtopic_code,
                    "description": row.subtopic_description,
                    "materials": {}
                }
            
            # Add material information if available
            if row.material_id:
                category_id = row.category_id
                if category_id not in courses[course_id]["subjects"][subject_id]["topics"][topic_id]["subtopics"][subtopic_id]["materials"]:
                    courses[course_id]["subjects"][subject_id]["topics"][topic_id]["subtopics"][subtopic_id]["materials"][category_id] = {
                        "id": category_id,
                        "name": row.category_name,
                        "code": row.category_code,
                        "description": row.category_description,
                        "is_protected": bool(row.is_protected),
                        "material_category_id": row.material_category_id,
                        "files": []
                    }
                
                # Add file information
                courses[course_id]["subjects"][subject_id]["topics"][topic_id]["subtopics"][subtopic_id]["materials"][category_id]["files"].append({
                    "id": row.material_id,
                    "name": row.material_name,
                    "path": row.material_path,
                    "extension_type": row.extension_type,
                    "video_duration": row.video_duration,
                    "file_size": row.file_size,
                    "material_category_id": row.material_category_id
                })
        
        # Convert dictionaries to lists for JSON serialization
        for course_id in courses:
            courses[course_id]["subjects"] = list(courses[course_id]["subjects"].values())
            for subject in courses[course_id]["subjects"]:
                subject["topics"] = list(subject["topics"].values())
                for topic in subject["topics"]:
                    topic["subtopics"] = list(topic["subtopics"].values())
                    for subtopic in topic["subtopics"]:
                        subtopic["materials"] = list(subtopic["materials"].values())
        
        return jsonify({
            "status": "success",
            "message": "Approved courses retrieved successfully",
            "data": {
                "courses": list(courses.values())
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_approved_courses: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@courses_bp.route('/api/course-structure', methods=['GET'])
@jwt_required()
def get_course_structure():
    """Get complete course structure including courses, subjects, topics, and subtopics"""
    try:
        # Get optional filter parameters
        course_id = request.args.get('course_id', type=int)
        subject_id = request.args.get('subject_id', type=int)
        topic_id = request.args.get('topic_id', type=int)
        nested = request.args.get('nested', 'false').lower() == 'true'
        
        # Base queries
        courses_query = db_session.query(Course).filter(Course.deleted_at.is_(None))
        subjects_query = db_session.query(Subject).filter(Subject.is_active == True)
        topics_query = db_session.query(Topic).filter(Topic.is_active == True)
        subtopics_query = db_session.query(SubTopic).filter(SubTopic.is_active == True)
        
        # Apply filters if provided
        if course_id:
            courses_query = courses_query.filter(Course.id == course_id)
            subjects_query = subjects_query.filter(Subject.course_id == course_id)
            # For topics and subtopics, we need to join with subjects to filter by course_id
            topics_query = topics_query.join(Subject, Topic.subject_id == Subject.id).filter(Subject.course_id == course_id)
            subtopics_query = subtopics_query.join(Topic, SubTopic.topic_id == Topic.id).join(Subject, Topic.subject_id == Subject.id).filter(Subject.course_id == course_id)
        
        if subject_id:
            subjects_query = subjects_query.filter(Subject.id == subject_id)
            topics_query = topics_query.filter(Topic.subject_id == subject_id)
            subtopics_query = subtopics_query.join(Topic, SubTopic.topic_id == Topic.id).filter(Topic.subject_id == subject_id)
        
        if topic_id:
            topics_query = topics_query.filter(Topic.id == topic_id)
            subtopics_query = subtopics_query.filter(SubTopic.topic_id == topic_id)
        
        # Execute queries
        courses = courses_query.all()
        subjects = subjects_query.all()
        topics = topics_query.all()
        subtopics = subtopics_query.all()
        
        if nested:
            # Create a dictionary to store subjects by course
            subjects_dict = {}
            for subject in subjects:
                if subject.course_id not in subjects_dict:
                    subjects_dict[subject.course_id] = []
                subjects_dict[subject.course_id].append({
                    "id": str(subject.id),
                    "course_id": str(subject.course_id),
                    "name": subject.name,
                    "code": subject.code,
                    "description": subject.description,
                    "price": subject.current_price,
                    "credits": None,  # Not present in current model
                    "status": "active" if subject.is_active else "inactive",
                    "created_at": subject.created_at.isoformat() if subject.created_at else None,
                    "updated_at": subject.updated_at.isoformat() if subject.updated_at else None,
                    "topics": []
                })
            
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
            nested_courses = []
            for course in courses:
                course_subjects = []
                for subject in subjects:
                    if subject.course_id == course.id:
                        subject_data = {
                            "id": str(subject.id),
                            "course_id": str(subject.course_id),
                            "name": subject.name,
                            "code": subject.code,
                            "description": subject.description,
                            "price": subject.current_price,
                            "credits": None,  # Not present in current model
                            "status": "active" if subject.is_active else "inactive",
                            "created_at": subject.created_at.isoformat() if subject.created_at else None,
                            "updated_at": subject.updated_at.isoformat() if subject.updated_at else None,
                            "topics": topics_dict.get(subject.id, [])
                        }
                        course_subjects.append(subject_data)
                
                nested_courses.append({
                    "id": str(course.id),
                    "name": course.name,
                    "code": course.code,
                    "description": course.description,
                    "duration": None,  # Not present in current model
                    "banner_image": None,  # Not present in current model
                    "status": "active" if course.deleted_at is None else "inactive",
                    "certification": None,  # Not present in current model
                    "created_at": course.created_at.isoformat() if course.created_at else None,
                    "updated_at": course.updated_at.isoformat() if course.updated_at else None,
                    "subjects": course_subjects
                })
            
            response = {
                "courses": nested_courses
            }
        else:
            response = {
                "courses": [
                    {
                        "id": str(course.id),
                        "name": course.name,
                        "code": course.code,
                        "description": course.description,
                        "duration": None,  # Not present in current model
                        "banner_image": None,  # Not present in current model
                        "status": "active" if course.deleted_at is None else "inactive",
                        "certification": None,  # Not present in current model
                        "created_at": course.created_at.isoformat() if course.created_at else None,
                        "updated_at": course.updated_at.isoformat() if course.updated_at else None
                    }
                    for course in courses
                ],
                "subjects": [
                    {
                        "id": str(subject.id),
                        "course_id": str(subject.course_id),
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
            "message": "Course structure retrieved successfully",
            "data": response
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500 