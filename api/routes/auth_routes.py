from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, unset_jwt_cookies
from database.db_connector import get_db
from auth.controllers.auth_controller import auth
from auth.controllers.users_controller import UsersController
from auth.models.schemas import UserCreate, UserUpdate, UserResponse
from auth.middleware.token_middleware import token_refresh_middleware
from auth.services.device_fingerprint_service import DeviceFingerprintService
from auth.models.models import User, UserDevice, UserRole, Role

auth_bp = Blueprint('auth', __name__)

# Register the existing auth blueprint
auth_bp.register_blueprint(auth)

# Backend no longer refreshes tokens; frontend handles token lifecycle

# User routes
@auth_bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    db = get_db()
    try:
        user_data = UserCreate(**data)
        users_controller = UsersController(db)
        user = users_controller.create_user(user_data)
        return jsonify(user.dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@auth_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)
    current_user = get_jwt_identity()
    db = get_db()
    try:
        users_controller = UsersController(db)
        users = users_controller.get_users(skip, limit)
        return jsonify({
            "status": "success",
            "message": "Users retrieved successfully",
            "data": {
                "users": [user.dict() for user in users]
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@auth_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    current_user = get_jwt_identity()
    db = get_db()
    try:
        users_controller = UsersController(db)
        user = users_controller.get_user(user_id)
        return jsonify(user.dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 404
    finally:
        db.close()

@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user = get_jwt_identity()
    data = request.get_json()
    db = get_db()
    try:
        user_data = UserUpdate(**data)
        users_controller = UsersController(db)
        user = users_controller.update_user(user_id, user_data)
        return jsonify(user.dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@auth_bp.route('/user', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user's information"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        # Get user information
        db = get_db()
        users_controller = UsersController(db)
        user = users_controller.get_user(current_user_id)
        
        return jsonify({
            "status": "success",
            "message": "Current user retrieved successfully",
            "data": user.dict()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@auth_bp.route('/auth/logout', methods=['POST'])
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
        return jsonify({
            "status": "error",
            "message": "Logout failed",
            "error": str(e)
        }), 500

@auth_bp.route('/user-devices/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_devices(user_id):
    """Get all devices for a user"""
    try:
        # Get current user
        current_user_id = int(get_jwt_identity())  # Convert to int
        
        # Initialize device fingerprint service
        db = get_db()
        device_service = DeviceFingerprintService(db)
        
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
    finally:
        db.close()

@auth_bp.route('/user-devices/<int:device_id>/set-primary', methods=['PUT'])
@jwt_required()
def set_device_primary(device_id):
    """Set a device as primary while demoting others"""
    try:
        # Initialize device fingerprint service
        db = get_db()
        device_service = DeviceFingerprintService(db)
        
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
    finally:
        db.close()

@auth_bp.route('/user-devices/<int:device_id>/deactivate', methods=['PUT'])
@jwt_required()
def deactivate_device(device_id):
    """Deactivate a device"""
    try:
        # Initialize device fingerprint service
        db = get_db()
        device_service = DeviceFingerprintService(db)
        
        # Get current user from JWT
        current_user_id = int(get_jwt_identity())
        
        # Get device to verify ownership
        device = db.query(UserDevice).filter(
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
            current_user = db.query(User).filter(User.id == current_user_id).first()
            if not current_user:
                return jsonify({
                    "status": "error",
                    "message": "User not found"
                }), 404
                
            # Check if user has SYSADMIN role
            user_roles = db.query(UserRole).join(Role).filter(
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
    finally:
        db.close() 