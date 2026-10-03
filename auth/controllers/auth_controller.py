from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from database.db_connector import db_session
from auth.models.models import User, UserRole, Role, UserDevice
from auth.models.schemas import UserResponse
from datetime import datetime
from pydantic import BaseModel, EmailStr, validator
import logging
from functools import wraps
from typing import Optional
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, unset_jwt_cookies, decode_token
from werkzeug.security import generate_password_hash, check_password_hash
from auth.services.device_fingerprint_service import DeviceFingerprintService
from auth.services.login_session import (
    ONLINE_WINDOW,
    assign_login_session,
    create_login_token,
    session_was_replaced,
    touch_last_seen,
)
from public.controllers.sms_controller import SMSService
import random
import string

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

# Validation schemas
class LoginRequest(BaseModel):
    login: str  # Can be email or phone
    password: str

    @validator('password')
    def password_length(cls, v):
        if len(v) < 5:
            raise ValueError('Password must be at least 5 characters long')
        return v

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

    @validator('new_password')
    def password_length(cls, v):
        if len(v) < 5:
            raise ValueError('New password must be at least 5 characters long')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

    @validator('new_password')
    def password_different(cls, v, values):
        if 'old_password' in values and v == values['old_password']:
            raise ValueError('New password must be different from old password')
        return v

@auth.route('/auth/login', methods=['POST'])
def login():
    try:
        # Get JSON data and validate
        data = request.get_json()
        logger.info(f"Received login request with data: {data}")
        
        try:
            login_data = LoginRequest(**data)
            logger.info(f"Login data validated successfully: {login_data}")
        except Exception as e:
            logger.warning(f"Login validation failed: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Validation failed",
                "errors": str(e)
            }), 422

        logger.info(f"Login attempt with: {login_data.login}")

        # Find user by email or phone
        user = db_session.query(User).filter(
            (User.email == login_data.login) | (User.phone == login_data.login)
        ).first()

        if not user:
            logger.warning(f"User not found for login: {login_data.login}")
            return jsonify({
                "status": "error",
                "message": "Login failed",
                "errors": {"login": ["Invalid credentials"]}
            }), 401

        logger.info(f"User found: ID={user.id}, Email={user.email}, Status={user.status}")

        # Check if user is active
        if user.status != 'ACTIVE':
            logger.warning(f"Inactive account login attempt for user_id: {user.id}")
            return jsonify({
                "status": "error",
                "message": "Login failed",
                "errors": {"login": ["Account is not active"]}
            }), 401

        # Verify password
        logger.info(f"Verifying password for user_id: {user.id}")
        password_valid = check_password_hash(user.password, login_data.password)
        logger.info(f"Password verification result: {password_valid}")
        logger.info(f"Password hash in DB: {user.password}")

        if not password_valid:
            logger.warning(f"Invalid password attempt for user_id: {user.id}")
            return jsonify({
                "status": "error",
                "message": "Login failed",
                "errors": {"login": ["Invalid credentials"]}
            }), 401

        try:
            # Get user roles
            logger.info(f"Fetching roles for user_id: {user.id}")
            
            # First check if there are any user roles at all
            all_user_roles = db_session.query(UserRole).filter(UserRole.user_id == user.id).all()
            logger.info(f"Total user roles found for user {user.id}: {len(all_user_roles)}")
            
            # Log details of each user role
            for ur in all_user_roles:
                logger.info(f"UserRole ID: {ur.id}, Role ID: {ur.role_id}, Is Active: {ur.is_active}, Deleted At: {ur.deleted_at}")
            
            # Now get the filtered roles
            user_roles = db_session.query(UserRole).join(Role).filter(
                UserRole.user_id == user.id,
                UserRole.is_active == True,
                UserRole.deleted_at.is_(None),
                Role.deleted_at.is_(None)
            ).all()
            
            logger.info(f"Filtered active user roles found: {len(user_roles)}")
            for ur in user_roles:
                logger.info(f"Active UserRole ID: {ur.id}, Role Name: {ur.role.name}, Role Code: {ur.role.code}")

            # New login replaces any session still open on another device.
            session_id = assign_login_session(user)
            db_session.commit()
            access_token = create_login_token(user, session_id)
            logger.info(f"JWT token created successfully for user_id: {user.id}")

            # Prepare response
            response_data = {
                "status": "success",
                "message": "Login successful",
                "data": {
                    "token": access_token,
                    "session_id": session_id,
                    "user": {
                        "id": user.id,
                        "first_name": user.first_name,
                        "middle_name": user.middle_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "phone": user.phone,
                        "status": user.status,
                        "reset_password": user.reset_password,
                        "assignedRoles": [{
                            "id": ur.role_id,
                            "is_default": ur.is_default,
                            "name": ur.role.name,
                            "code": ur.role.code
                        } for ur in user_roles]
                    }
                }
            }

            logger.info(f"Login successful for user_id: {user.id}")
            return jsonify(response_data), 200

        except Exception as e:
            db_session.rollback()
            logger.error(f"Token creation failed for user_id: {user.id}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Token creation failed",
                "error": str(e)
            }), 500

    except Exception as e:
        logger.error("Login failed with server error", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Login failed, server error",
            "error": str(e)
        }), 500


def _current_page(body) -> Optional[str]:
    raw = _request_value(body, "page")
    if not isinstance(raw, str):
        return None
    page = raw.strip()
    if not page:
        return None
    return page[:500]


def _request_value(body, name):
    if body.get(name) is not None:
        return body.get(name)
    return request.args.get(name)


def _presented_login(body):
    """
    Identify the caller's login from a JWT or from user id plus session id.

    The JWT may be the Authorization bearer token or a ``token`` field.
    ``user_id`` alone is not enough: every device shares it, so the client
    must also send the ``session_id`` returned at login.
    """
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raw = _request_value(body, "token")
        token = raw.strip() if isinstance(raw, str) else None

    requested_user_id = _request_value(body, "user_id")
    requested_session_id = _request_value(body, "session_id")
    if isinstance(requested_session_id, str):
        requested_session_id = requested_session_id.strip() or None

    if token:
        try:
            claims = decode_token(token, allow_expired=True)
        except Exception:
            return None, None, "invalid_token"
        try:
            user_id = int(claims.get("sub"))
        except (TypeError, ValueError):
            return None, None, "invalid_token"
        if requested_user_id is not None:
            try:
                if int(requested_user_id) != user_id:
                    return None, None, "user_mismatch"
            except (TypeError, ValueError):
                return None, None, "invalid_user"
        session_id = claims.get("sid") or requested_session_id
        return user_id, session_id, None

    if requested_user_id is None:
        return None, None, "missing_identity"
    if not requested_session_id:
        return None, None, "missing_session"
    try:
        return int(requested_user_id), requested_session_id, None
    except (TypeError, ValueError):
        return None, None, "invalid_user"


@auth.route('/auth/session-status', methods=['GET', 'POST'])
def session_status():
    """
    Tell the client whether this login was replaced by a newer one.

    Call with ``Authorization: Bearer <jwt>``, or with ``user_id`` and the
    ``session_id`` stored from the login response. A match means this browser
    is still the active login. A mismatch means the account signed in again
    somewhere else and this client should sign out.
    """
    body = request.get_json(silent=True) or {}
    user_id, session_id, error = _presented_login(body)

    if error == "invalid_token":
        return jsonify({
            "status": "error",
            "message": "Invalid token"
        }), 401
    if error == "user_mismatch":
        return jsonify({
            "status": "error",
            "message": "Token does not belong to this user"
        }), 400
    if error == "missing_identity":
        return jsonify({
            "status": "error",
            "message": "Provide a JWT token, or user_id together with session_id"
        }), 400
    if error == "missing_session":
        return jsonify({
            "status": "error",
            "message": "session_id is required when checking by user_id"
        }), 400
    if error == "invalid_user":
        return jsonify({
            "status": "error",
            "message": "user_id must be a number"
        }), 400

    user = db_session.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        return jsonify({
            "status": "error",
            "message": "User not found"
        }), 404

    replaced = session_was_replaced(user.active_session_id, session_id)
    if replaced:
        message = "Another login was detected on a different device or browser."
    else:
        message = "This session is still the active login."
        try:
            if touch_last_seen(user, page=_current_page(body)):
                db_session.commit()
        except Exception:
            db_session.rollback()
            logger.exception("Failed to record last_seen for user_id=%s", user.id)

    return jsonify({
        "status": "success",
        "message": message,
        "data": {
            "user_id": user.id,
            "another_login_detected": replaced,
            "session_valid": not replaced
        }
    }), 200


@auth.route('/auth/online-count', methods=['GET'])
def online_count():
    """Count users whose latest valid session check is still inside the online window."""
    cutoff = datetime.utcnow() - ONLINE_WINDOW
    count = db_session.query(User).filter(
        User.deleted_at.is_(None),
        User.last_seen_at.isnot(None),
        User.last_seen_at >= cutoff,
    ).count()

    return jsonify({
        "status": "success",
        "data": {
            "online_users": count,
            "window_seconds": int(ONLINE_WINDOW.total_seconds()),
        }
    }), 200


@auth.route('/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    try:
        # Get JSON data and validate
        data = request.get_json()
        try:
            password_data = ChangePasswordRequest(**data)
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": "Validation failed",
                "errors": str(e)
            }), 422

        # Get user from database using the identity from the token
        user_id = get_jwt_identity()  # This will be a string
        user = db_session.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 404

        # Verify old password
        if not check_password_hash(user.password, password_data.old_password):
            return jsonify({
                "status": "error",
                "message": "Password change failed",
                "errors": {"old_password": ["The old password is incorrect"]}
            }), 422

        try:
            # Update password
            user.password = generate_password_hash(password_data.new_password, method='pbkdf2:sha256')
            user.reset_password = False
            user.updated_at = datetime.utcnow()
            
            db_session.commit()

            return jsonify({
                "status": "success",
                "message": "Password changed successfully"
            }), 200

        except Exception as e:
            db_session.rollback()
            logger.error(f"Password change failed for user_id: {user_id}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Password change failed",
                "error": str(e)
            }), 500

    except Exception as e:
        logger.error("Password change failed with server error", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Password change failed, server error",
            "error": str(e)
        }), 500

@auth.route('/api/user-devices/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_devices(user_id):
    """Get all devices for a user"""
    try:
        # Get current user
        current_user_id = int(get_jwt_identity())  # Convert to int
        
        # Initialize device fingerprint service
        device_service = DeviceFingerprintService(db_session)
        
        # Get devices
        devices = device_service.get_user_devices(user_id)
        
        # Serialize devices
        serialized_devices = []
        for device in devices:
            serialized_devices.append({
                "id": device.id,
                "user_id": device.user_id,
                "visitor_id": device.visitor_id,
                "browser_name": device.browser_name,
                "browser_version": device.browser_version,
                "os_name": device.os_name,
                "os_version": device.os_version,
                "hardware_info": device.hardware_info,
                "is_primary": device.is_primary,
                "last_used": device.last_used.isoformat() if device.last_used else None,
                "created_at": device.created_at.isoformat() if device.created_at else None,
                "updated_at": device.updated_at.isoformat() if device.updated_at else None
            })
        
        return jsonify({
            "status": "success",
            "data": {
                "devices": serialized_devices
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@auth.route('/api/user-devices/<int:device_id>/set-primary', methods=['PUT'])
@jwt_required()
def set_device_primary(device_id):
    """Set a device as primary while demoting others"""
    try:
        # Initialize device fingerprint service
        device_service = DeviceFingerprintService(db_session)
        
        # Get current user from JWT
        current_user_id = int(get_jwt_identity())
        
        # Update device status
        device = device_service.update_device_status(device_id, True, current_user_id)
        
        if not device:
            return jsonify({
                "status": "error",
                "message": "Device not found"
            }), 404
            
        # Serialize device
        serialized_device = {
            "id": device.id,
            "user_id": device.user_id,
            "visitor_id": device.visitor_id,
            "browser_name": device.browser_name,
            "browser_version": device.browser_version,
            "os_name": device.os_name,
            "os_version": device.os_version,
            "hardware_info": device.hardware_info,
            "is_primary": device.is_primary,
            "last_used": device.last_used.isoformat() if device.last_used else None,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "updated_at": device.updated_at.isoformat() if device.updated_at else None
        }
        
        return jsonify({
            "status": "success",
            "message": "Device made primary successfully",
            "data": serialized_device
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@auth.route('/api/user-devices/<int:device_id>/deactivate', methods=['PUT'])
@jwt_required()
def deactivate_device(device_id):
    """Deactivate a device"""
    try:
        # Initialize device fingerprint service
        device_service = DeviceFingerprintService(db_session)
        
        # Get current user from JWT
        current_user_id = int(get_jwt_identity())
        
        # Get device to verify ownership
        device = db_session.query(UserDevice).filter(
            UserDevice.id == device_id,
            UserDevice.is_active == True
        ).first()
        
        if not device:
            return jsonify({
                "status": "error",
                "message": "Device not found"
            }), 404
            
        # Only allow users to deactivate their own devices or admin users
        if device.user_id != current_user_id:
            # Check if current user is admin
            current_user = db_session.query(User).filter(User.id == current_user_id).first()
            if not current_user:
                return jsonify({
                    "status": "error",
                    "message": "User not found"
                }), 404
                
            # Check if user has SYSADMIN role
            user_roles = db_session.query(UserRole).join(Role).filter(
                UserRole.user_id == current_user_id,
                UserRole.is_active == True,
                UserRole.deleted_at.is_(None),
                Role.deleted_at.is_(None),
                Role.name == 'SYSADMIN'
            ).all()
            
            if not user_roles:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized to deactivate other user's devices"
                }), 403
        
        # Deactivate device
        device = device_service.deactivate_device(device_id, device.user_id, current_user_id)
        
        if not device:
            return jsonify({
                "status": "error",
                "message": "Failed to deactivate device"
            }), 500
            
        # Serialize device
        serialized_device = {
            "id": device.id,
            "user_id": device.user_id,
            "visitor_id": device.visitor_id,
            "browser_name": device.browser_name,
            "browser_version": device.browser_version,
            "os_name": device.os_name,
            "os_version": device.os_version,
            "hardware_info": device.hardware_info,
            "is_primary": device.is_primary,
            "is_active": device.is_active,
            "last_used": device.last_used.isoformat() if device.last_used else None,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "updated_at": device.updated_at.isoformat() if device.updated_at else None
        }
        
        return jsonify({
            "status": "success",
            "message": "Device deactivated successfully",
            "data": serialized_device
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@auth.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout the current user by invalidating their JWT token"""
    try:
        # Get the JWT token
        jti = get_jwt()["jti"]
        
        # Add the token to the blacklist
        # Note: In a production environment, you should use Redis or another
        # persistent storage for the blacklist
        # For now, we'll just return success
        # TODO: Implement token blacklisting with Redis
        
        # Create response
        response = jsonify({
            "status": "success",
            "message": "Successfully logged out"
        })
        
        # Unset the JWT cookies
        unset_jwt_cookies(response)
        
        return response, 200
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Logout failed",
            "error": str(e)
        }), 500

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

@auth.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password for a user and send it via SMS using their registered phone number"""
    try:
        # Get JSON data
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                "status": "error",
                "message": "Email is required"
            }), 400

        email = data['email']
        logger.info(f"Password reset requested for email: {email}")
        
        # Find user by email
        user = db_session.query(User).filter(User.email == email).first()
        
        if not user:
            logger.warning(f"User not found for email: {email}")
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 404

        logger.info(f"User found: ID={user.id}, Email={user.email}, Phone={user.phone}")

        # Generate a random 6-digit password
        new_password = ''.join(random.choices(string.digits, k=6))
        logger.info(f"Generated new password: {new_password}")
        
        try:
            # Update password and set reset_password flag to 1 (True)
            user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            user.reset_password = 1  # Set to 1 (True) to indicate password needs to be changed
            user.updated_at = datetime.utcnow()
            
            # Format the phone number
            formatted_phone = format_phone_number(user.phone)
            logger.info(f"Original phone: {user.phone}, Formatted phone: {formatted_phone}")
            
            db_session.commit()
            logger.info(f"Password updated for user ID: {user.id}")

            # Send SMS with new password
            message = f"Your password for The African Hub has been reset. Your new password is: {new_password}. Please log in and change it."
            logger.info(f"Sending SMS to {formatted_phone} with message: {message}")
            
            sms_result = SMSService.send_message(
                phone=formatted_phone,
                message=message,
                process_name='password_reset',
            )
            
            logger.info(f"SMS sending result: {sms_result}")

            return jsonify({
                "status": "success",
                "message": "Password reset successful. New password has been sent to your registered phone number."
            }), 200

        except Exception as e:
            db_session.rollback()
            logger.error(f"Password reset failed for user_id: {user.id}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Password reset failed",
                "error": str(e)
            }), 500

    except Exception as e:
        logger.error("Password reset failed with server error", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Password reset failed, server error",
            "error": str(e)
        }), 500 