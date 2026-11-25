from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from study_access.services.access_service import material_block


def optional_user_id():
    verify_jwt_in_request(optional=True)
    identity = get_jwt_identity()
    if identity is None:
        return None
    return int(identity)


def block_material_response(db, material_id: int):
    """Return a 403 response when the caller cannot study this material."""
    user_id = optional_user_id()
    if user_id is None:
        return None
    block = material_block(db, user_id, material_id)
    if not block:
        return None
    return jsonify({"status": "error", "message": block["message"], "code": block["code"]}), 403
