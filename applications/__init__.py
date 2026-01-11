from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from database.db_connector import init_db
from applications.controllers.applications_controller import applications_bp
from auth.controllers.auth_controller import auth
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # JWT configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    jwt = JWTManager(app)
    
    # Initialize database
    init_db()
    
    # Register blueprints
    app.register_blueprint(auth)
    app.register_blueprint(applications_bp)
    
    return app 