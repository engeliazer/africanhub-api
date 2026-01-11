from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import db_session
from auth.services.device_fingerprint_service import DeviceFingerprintService
from auth.models.schemas import UserDeviceInDB
from typing import List

device_bp = Blueprint('devices', __name__)

@device_bp.route('/devices/user/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_devices(user_id: int):
    """Get all devices for a user"""
    try:
        current_user_id = get_jwt_identity()
        
        # TODO: Add admin check here
        
        device_service = DeviceFingerprintService(db_session)
        devices = device_service.get_user_devices(user_id)
        
        return jsonify({
            "status": "success",
            "data": [UserDeviceInDB.from_orm(device).dict() for device in devices]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@device_bp.route('/devices/<int:device_id>/status', methods=['PUT'])
@jwt_required()
def update_device_status(device_id: int):
    """Update device primary status"""
    try:
        current_user_id = get_jwt_identity()
        
        # TODO: Add admin check here
        
        data = request.get_json()
        is_primary = data.get('is_primary', False)
        
        device_service = DeviceFingerprintService(db_session)
        device = device_service.update_device_status(device_id, is_primary, current_user_id)
        
        if not device:
            return jsonify({
                "status": "error",
                "message": "Device not found"
            }), 404
            
        return jsonify({
            "status": "success",
            "data": UserDeviceInDB.from_orm(device).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500 