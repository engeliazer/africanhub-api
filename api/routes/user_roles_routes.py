from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import get_db
from auth.controllers.user_roles_controller import UserRolesController
from auth.models.schemas import UserRoleCreate, UserRoleResponse

user_roles_bp = Blueprint('user_roles', __name__)

@user_roles_bp.route('/user-roles', methods=['POST'])
@jwt_required()
def create_user_role():
    print("Received request to create user role")  # Debug log
    data = request.get_json()
    print(f"Request data: {data}")  # Debug log
    
    # Get the current user's ID from the JWT token
    current_user_id = get_jwt_identity()
    
    # Check if user is trying to assign a role to themselves
    if int(data.get('user_id')) == int(current_user_id):
        return jsonify({
            "status": "error",
            "message": "Users cannot assign roles to themselves for security reasons"
        }), 403
    
    db = get_db()
    try:
        user_role_data = UserRoleCreate(**data)
        controller = UserRolesController(db)
        user_role = controller.create_user_role(user_role_data)
        print(f"Successfully created user role: {user_role.dict()}")  # Debug log
        return jsonify(user_role.dict()), 201
    except Exception as e:
        print(f"Error creating user role: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@user_roles_bp.route('/user-roles', methods=['GET'])
@jwt_required()
def get_user_roles():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)
    db = get_db()
    try:
        controller = UserRolesController(db)
        user_roles = controller.get_user_roles(skip, limit)
        return jsonify([ur.dict() for ur in user_roles])
    finally:
        db.close()

@user_roles_bp.route('/user-roles/<int:user_role_id>', methods=['GET'])
@jwt_required()
def get_user_role(user_role_id):
    db = get_db()
    try:
        controller = UserRolesController(db)
        user_role = controller.get_user_role(user_role_id)
        return jsonify(user_role.dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 404
    finally:
        db.close()

@user_roles_bp.route('/users/<int:user_id>/roles', methods=['GET'])
@jwt_required()
def get_user_roles_by_user(user_id):
    db = get_db()
    try:
        controller = UserRolesController(db)
        user_roles = controller.get_roles_by_user(user_id)
        return jsonify([ur.dict() for ur in user_roles])
    finally:
        db.close()

@user_roles_bp.route('/user-roles/<int:user_role_id>', methods=['PUT'])
@jwt_required()
def update_user_role(user_role_id):
    data = request.get_json()
    db = get_db()
    try:
        user_role_data = UserRoleCreate(**data)
        controller = UserRolesController(db)
        user_role = controller.update_user_role(user_role_id, user_role_data)
        return jsonify(user_role.dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@user_roles_bp.route('/user-roles/<int:user_role_id>', methods=['DELETE'])
@jwt_required()
def delete_user_role(user_role_id):
    print(f"Received request to delete user role with ID: {user_role_id}")  # Debug log
    db = get_db()
    try:
        controller = UserRolesController(db)
        controller.delete_user_role(user_role_id)
        print(f"Successfully deleted user role with ID: {user_role_id}")  # Debug log
        return jsonify({"message": "User role deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting user role: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 400
    finally:
        db.close() 