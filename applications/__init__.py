import os

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager


def create_app():
    # Imported here so loading application models does not pull this controller
    # back into study_access while that module is still initializing.
    from applications.controllers.applications_controller import applications_bp
    from auth.controllers.auth_controller import auth
    from database.db_connector import init_db

    app = Flask(__name__)
    CORS(app)

    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    JWTManager(app)

    init_db()

    app.register_blueprint(auth)
    app.register_blueprint(applications_bp)

    return app 