from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from database.db_connector import get_db
from auth.controllers.roles_controller import RolesController
from auth.models.schemas import RoleCreate, RoleInDB

roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/roles', methods=['GET'])
@jwt_required()
def get_roles():
    """Get all roles"""
    db = get_db()
    try:
        roles_controller = RolesController()
        roles = roles_controller.get_roles(db)
        return jsonify({
            "status": "success",
            "message": "Roles retrieved successfully",
            "data": {
                "roles": [role.dict() for role in roles]
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@roles_bp.route('/roles/<int:role_id>', methods=['GET'])
@jwt_required()
def get_role(role_id):
    """Get a specific role by ID"""
    try:
        db = get_db()
        roles_controller = RolesController()
        role = roles_controller.get_role(db, role_id)
        if role is None:
            return jsonify({"message": "Role not found"}), 404
        return jsonify(role.dict()), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()

@roles_bp.route('/roles', methods=['POST'])
@jwt_required()
def create_role():
    """Create a new role"""
    try:
        data = request.get_json()
        db = get_db()
        roles_controller = RolesController()
        role = roles_controller.create_role(db, RoleCreate(**data))
        return jsonify({
            "status": "success",
            "message": "Role created successfully",
            "data": role.dict()
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close() 