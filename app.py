from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy.orm import Session
from typing import List
from functools import wraps
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, verify_jwt_in_request
from datetime import timedelta
import secrets

from database.db_connector import DBConnector, init_db, db_session
from auth.models.models import User
from auth.models.schemas import (
    UserCreate, UserUpdate, UserResponse,
    UserRoleCreate, UserRoleResponse,
    RoleInDB, RoleCreate
)
from auth.controllers.users_controller import UsersController
from auth.controllers.user_roles_controller import UserRolesController
from auth.controllers.roles_controller import RolesController
from security.jwt_handler import JWTHandler
from public.controllers.self_registration_controller import public
from auth.controllers.auth_controller import auth
from database.db_connector import db_session
from subjects.models.models import Season, Subject, Topic, SubTopic, SeasonSubject, SeasonApplicant, ApplicationStatus
from subjects.models.schemas import (
    SeasonCreate, SeasonUpdate, SeasonInDB,
    SubjectCreate, SubjectUpdate, SubjectInDB,
    TopicCreate, TopicUpdate, TopicInDB,
    SubTopicCreate, SubTopicUpdate, SubTopicInDB,
    SeasonSubjectCreate, SeasonSubjectUpdate, SeasonSubjectInDB,
    SeasonApplicantCreate, SeasonApplicantUpdate, SeasonApplicantInDB
)
from studies.models.models import StudyMaterialCategory, SubtopicMaterial
from studies.models.schemas import (
    StudyMaterialCategoryCreate, StudyMaterialCategoryUpdate, StudyMaterialCategoryInDB,
    SubtopicMaterialCreate, SubtopicMaterialUpdate, SubtopicMaterialInDB
)
from studies.controllers.material_categories_controller import material_categories_bp
from studies.controllers.subtopic_materials_controller import subtopic_materials_bp
from applications.models.models import Application, PaymentStatus as ApplicationPaymentStatus
from applications.models.schemas import ApplicationCreate, ApplicationUpdate, ApplicationInDB
from applications.controllers.applications_controller import applications_bp
from applications.controllers.accounting_controller import accounting_bp
from chat.controllers.chat_controller import chat_bp
from auth.routes.device_routes import device_bp
from api.routes.monitoring_routes import monitoring_bp
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from config import UPLOAD_FOLDER, allowed_file
import os
import uuid
import re
import hashlib
import hmac

# Import blueprints from new route files
from api.routes.auth_routes import auth_bp
from api.routes.user_roles_routes import user_roles_bp
from api.routes.roles_routes import roles_bp
from api.routes.subjects_routes import (
    subjects_bp, topics_bp, subtopics_bp
)
from subjects.controllers.courses_controller import courses_bp as subjects_courses_bp
from instructors.controllers.instructors_controller import instructors_bp
from testimonials.controllers.testimonials_controller import testimonials_bp
from api.routes.study_routes import material_categories_bp
from api.routes.application_routes import applications_bp, payments_bp
from public.controllers.sms_controller import sms_bp
from public.controllers.contact_controller import contact_bp
from api.routes.bank_reconciliation_routes import bank_reconciliation_bp
from auth.middleware.token_middleware import token_refresh_middleware, add_refreshed_token_to_response
from api.routes.vdocipher_routes import vdocipher_bp

app = Flask(__name__)

# Generate a secure secret key if not provided in environment
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))

# Configure JWT
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # No expiration - frontend handles session timeout
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'
app.config['JWT_JSON_KEY'] = 'access_token'
app.config['JWT_IDENTITY_CLAIM'] = 'sub'

# Token refresh middleware disabled since tokens don't expire
# Frontend handles session timeout and idle logout
# @app.before_request
# def apply_token_refresh():
#     token_refresh_middleware()

# @app.after_request
# def add_token_to_response(response):
#     response = add_refreshed_token_to_response(response)
#     return response

# Configure maximum file upload size (1000MB = 1GB)
app.config['MAX_CONTENT_LENGTH'] = 1200 * 1024 * 1024  # 1000MB in bytes

# Configure timeouts for large file uploads
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for file downloads
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)  # Session timeout
app.config['UPLOAD_TIMEOUT'] = 3600  # 1 hour timeout for uploads

# Configure request timeouts
app.config['REQUEST_TIMEOUT'] = 3600  # 1 hour timeout for requests
app.config['PROPAGATE_EXCEPTIONS'] = True  # Propagate exceptions to error handlers

# Add a before_request handler to set timeouts
@app.before_request
def before_request():
    # Set a longer timeout for the request
    if request.endpoint and 'upload' in request.endpoint:
        # Set a longer timeout for upload endpoints
        request.environ['wsgi.input'].timeout = 3600  # 1 hour timeout
        request.environ['wsgi.errors'].timeout = 3600  # 1 hour timeout

jwt = JWTManager(app)

# JWT callback to handle identity
@jwt.user_identity_loader
def user_identity_lookup(identity):
    return str(identity)

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return db_session.query(User).filter(User.id == int(identity)).first()

# Configure CORS with specific settings
# NOTE: CORS is handled by nginx in production to avoid duplicate headers
# Uncomment this if running without nginx (e.g., local development)
# CORS(app, resources={
#     r"/*": {  # Apply to all routes
#         "origins": "*",  # Allow all origins (for testing - restrict in production)
#         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#         "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-Token"],
#         "supports_credentials": True,
#         "expose_headers": ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "X-New-Token", "X-Token-Refreshed"],
#         "max_age": 3600  # Cache preflight requests for 1 hour
#     }
# })

# Add a global OPTIONS handler for all routes
# NOTE: OPTIONS requests are handled by nginx in production
# Uncomment this if running without nginx (e.g., local development)
# @app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
# @app.route('/<path:path>', methods=['OPTIONS'])
# def handle_options(path):
#     response = app.response_class(status=204)
#     origin = request.headers.get('Origin')
#     response.headers['Access-Control-Allow-Origin'] = origin or '*'
#     response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
#     response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRF-Token'
#     response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges, X-New-Token, X-Token-Refreshed'
#     response.headers['Access-Control-Max-Age'] = '3600'
#     response.headers['Access-Control-Allow-Credentials'] = 'true'
#     return response

# Initialize database
init_db()

# Run database seeders
try:
    from database.seeder import run_seeders
    run_seeders(db_session())
except Exception as e:
    print(f"Error running seeders: {str(e)}")
finally:
    db_session.remove()

# Register blueprints
app.register_blueprint(public)
# app.register_blueprint(auth)  # Commenting out the original auth blueprint
app.register_blueprint(sms_bp)
app.register_blueprint(contact_bp)  # Public contact form (no auth required)

# Register new blueprints from route files
app.register_blueprint(auth_bp, url_prefix='/api', name='api_auth')
app.register_blueprint(user_roles_bp, url_prefix='/api', name='api_user_roles')
app.register_blueprint(roles_bp, url_prefix='/api', name='api_roles')
app.register_blueprint(subjects_bp, url_prefix='/api', name='api_subjects')
app.register_blueprint(topics_bp, url_prefix='/api', name='api_topics')
app.register_blueprint(subtopics_bp, url_prefix='/api', name='api_subtopics')
app.register_blueprint(subjects_courses_bp, name='subjects_courses')  # Contains /api/courses/approved (refactored to subjects)
app.register_blueprint(material_categories_bp, url_prefix='/api', name='api_material_categories')
app.register_blueprint(subtopic_materials_bp, url_prefix='/api', name='api_subtopic_materials')
app.register_blueprint(applications_bp, url_prefix='/api', name='api_applications')
app.register_blueprint(payments_bp, url_prefix='/api', name='api_payments')
app.register_blueprint(instructors_bp, url_prefix='/api', name='api_instructors')
app.register_blueprint(testimonials_bp, url_prefix='/api', name='api_testimonials')
app.register_blueprint(chat_bp, url_prefix='/api', name='api_chat')
app.register_blueprint(device_bp, url_prefix='/api', name='api_devices')
app.register_blueprint(accounting_bp, url_prefix='/api/accounting', name='api_accounting')
app.register_blueprint(bank_reconciliation_bp)
app.register_blueprint(monitoring_bp, url_prefix='/api', name='api_monitoring')
app.register_blueprint(vdocipher_bp, url_prefix='', name='api_vdocipher')  # VdoCipher routes already have /api prefix

# Print all registered routes for debugging
print("\nRegistered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule.rule}")

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "status": "error",
        "message": "Resource not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db_session.rollback()
    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500

# Cleanup database session
@app.teardown_appcontext
def cleanup(resp):
    db_session.remove()

# Add these constants after the app initialization
FILE_ACCESS_SECRET = os.environ.get('FILE_ACCESS_SECRET', 'your-secret-key-here')  # Should be set in environment
FILE_TOKEN_EXPIRY = int(os.environ.get('FILE_TOKEN_EXPIRY', 3600))  # Default 1 hour in seconds

def generate_file_access_token(filename, access_type):
    """Generate a secure, time-limited token for file access"""
    timestamp = int(datetime.utcnow().timestamp())
    expiry = timestamp + FILE_TOKEN_EXPIRY
    
    # Create the message to sign
    message = f"{filename}:{access_type}:{expiry}"
    
    # Create HMAC signature
    signature = hmac.new(
        FILE_ACCESS_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "token": signature,
        "expires": expiry,
        "filename": filename,
        "access_type": access_type
    }

def verify_file_access_token(filename, access_type, token, expires):
    """Verify the file access token"""
    if int(datetime.utcnow().timestamp()) > int(expires):
        return False
    
    # Recreate the message
    message = f"{filename}:{access_type}:{expires}"
    
    # Verify HMAC signature
    expected_signature = hmac.new(
        FILE_ACCESS_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(token, expected_signature)

# No automatic token refresh headers

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
