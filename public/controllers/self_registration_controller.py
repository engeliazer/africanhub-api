from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from database.db_connector import db_session
from auth.models.models import User, UserRole, Role
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token
import logging
import random
import string
from sqlalchemy import text
from public.controllers.sms_controller import SMSService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

public = Blueprint('public', __name__)

def generate_password(length=6):
    """Generate a random numeric password"""
    return ''.join(random.choice(string.digits) for _ in range(length))

def format_phone_number(phone: str) -> str:
    """
    Format phone number to ensure it starts with 255 followed by the last 9 digits
    Example: 
    - "0755344162" -> "255755344162"
    - "255755344162" -> "255755344162"
    - "755344162" -> "255755344162"
    """
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # If the number starts with 255, return as is
    if digits.startswith('255'):
        return digits
    
    # If the number starts with 0, remove it
    if digits.startswith('0'):
        digits = digits[1:]
    
    # Ensure we have exactly 9 digits after 255
    if len(digits) > 9:
        digits = digits[-9:]  # Take last 9 digits
    
    # Add 255 prefix
    return f"255{digits}"

@public.route('/api/self-registration', methods=['POST'])
def self_registration():
    try:
        data = request.get_json()
        
        # Format phone number
        original_phone = data.get('phone')
        formatted_phone = format_phone_number(original_phone)
        logger.info(f"Original phone: {original_phone}, Formatted phone: {formatted_phone}")
        
        # Generate a random password
        plain_password = generate_password()
        # Use the default method (pbkdf2:sha256) for password hashing
        data['password'] = generate_password_hash(plain_password, method='pbkdf2:sha256')
        
        # Create new user
        new_user = User(
            first_name=data.get('first_name'),
            middle_name=data.get('middle_name'),
            last_name=data.get('last_name'),
            phone=formatted_phone,  # Use formatted phone number
            email=data.get('email'),
            password=data['password'],
            registration_mode='SELF',
            reset_password=True,  # Set to True for new registrations
            created_by=0,  # System user for self-registration
            updated_by=0,  # System user for self-registration
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db_session.add(new_user)
        db_session.commit()
        
        # Get STUDENT role
        student_role = db_session.query(Role).filter_by(code='STUDENT').first()
        if not student_role:
            raise Exception("STUDENT role not found in the system")

        # Create user role with STUDENT role
        user_role = UserRole(
            user_id=new_user.id,
            role_id=student_role.id,  # STUDENT role ID
            is_default=True,
            is_active=True,
            created_by=0,  # System user for self-registration
            updated_by=0,  # System user for self-registration
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(user_role)
        db_session.commit()

        # Create identity object for JWT
        identity = str(new_user.id)  # Convert user ID to string for JWT subject

        # Generate access token
        access_token = create_access_token(identity=identity)

        # Send welcome SMS with the new format
        welcome_message = f"Welcome to The African Hub. Your account is ready. Initial password: {plain_password}. Please log in to change it."

        SMSService.send_message(
            phone=formatted_phone,
            message=welcome_message,
        )

        return jsonify({
            "status": "success",
            "message": "Registration successful",
            "data": {
                "token": access_token,
                "user": {
                    "id": new_user.id,
                    "first_name": new_user.first_name,
                    "middle_name": new_user.middle_name,
                    "last_name": new_user.last_name,
                    "email": new_user.email,
                    "phone": formatted_phone,  # Return formatted phone number
                    "status": new_user.status,
                    "reset_password": new_user.reset_password,
                    "password": plain_password  # Include the plain password in the response
                }
            }
        }), 201

    except IntegrityError as e:
        db_session.rollback()
        return jsonify({
            "status": "error",
            "message": "Registration failed",
            "error": "Email already exists"
        }), 409
    except Exception as e:
        db_session.rollback()
        logger.error(f"Registration error: {str(e)}")  # Add error logging
        return jsonify({
            "status": "error",
            "message": "Registration failed",
            "error": str(e)
        }), 500 