from functools import wraps
from flask import request, jsonify
from .jwt_handler import JWTHandler

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"message": "Invalid token format"}), 401

        if not token:
            return jsonify({"message": "Token is missing"}), 401

        try:
            current_user = JWTHandler.get_current_user(token)
            return f(current_user, *args, **kwargs)
        except Exception as e:
            return jsonify({"message": "Invalid token"}), 401

    return decorated 