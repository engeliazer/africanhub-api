"""
Video tracking API routes — student watch progress for study materials.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database.db_connector import db_session
from video_tracking.controllers.tracking_controller import TrackingController

video_tracking_bp = Blueprint("video_tracking", __name__)


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _controller() -> TrackingController:
    return TrackingController(db_session)


def _error_response(result: dict):
    return jsonify({"status": "error", "message": result["error"]}), result["status_code"]


@video_tracking_bp.route("/api/video-tracking/sessions/start", methods=["POST"])
@jwt_required()
def start_session():
    data = request.get_json(silent=True) or {}
    material_id = data.get("material_id")

    if not material_id:
        return jsonify({"status": "error", "message": "material_id is required"}), 400

    try:
        material_id = int(material_id)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "material_id must be an integer"}), 400

    try:
        result = _controller().start_session(_current_user_id(), material_id)
        if "error" in result:
            return _error_response(result)
        return jsonify({"status": "success", "data": result}), 200
    except Exception:
        db_session.rollback()
        raise


@video_tracking_bp.route(
    "/api/video-tracking/sessions/<session_token>/heartbeat",
    methods=["POST"],
)
@jwt_required()
def heartbeat(session_token: str):
    data = request.get_json(silent=True) or {}

    if "current_position" not in data or "watched_delta" not in data:
        return jsonify(
            {
                "status": "error",
                "message": "current_position and watched_delta are required",
            }
        ), 400

    try:
        current_position = float(data["current_position"])
        watched_delta = float(data["watched_delta"])
    except (TypeError, ValueError):
        return jsonify(
            {
                "status": "error",
                "message": "current_position and watched_delta must be numbers",
            }
        ), 400

    result = _controller().heartbeat(
        user_id=_current_user_id(),
        session_token=session_token,
        current_position=current_position,
        watched_delta=watched_delta,
    )
    if "error" in result:
        return _error_response(result)

    return jsonify({"status": "success", "data": result}), 200


@video_tracking_bp.route(
    "/api/video-tracking/sessions/<session_token>/end",
    methods=["POST"],
)
@jwt_required()
def end_session(session_token: str):
    data = request.get_json(silent=True) or {}

    if "current_position" not in data or "watched_delta" not in data:
        return jsonify(
            {
                "status": "error",
                "message": "current_position and watched_delta are required",
            }
        ), 400

    try:
        current_position = float(data["current_position"])
        watched_delta = float(data["watched_delta"])
    except (TypeError, ValueError):
        return jsonify(
            {
                "status": "error",
                "message": "current_position and watched_delta must be numbers",
            }
        ), 400

    result = _controller().end_session(
        user_id=_current_user_id(),
        session_token=session_token,
        current_position=current_position,
        watched_delta=watched_delta,
    )
    if "error" in result:
        return _error_response(result)

    return jsonify({"status": "success", "data": result}), 200


@video_tracking_bp.route("/api/video-tracking/progress/<int:material_id>", methods=["GET"])
@jwt_required()
def get_material_progress(material_id: int):
    result = _controller().get_material_progress(_current_user_id(), material_id)
    if "error" in result:
        return _error_response(result)

    return jsonify({"status": "success", "data": result}), 200


@video_tracking_bp.route(
    "/api/video-tracking/progress/subject/<int:subject_id>",
    methods=["GET"],
)
@jwt_required()
def get_subject_progress(subject_id: int):
    result = _controller().get_subject_progress(_current_user_id(), subject_id)
    return jsonify({"status": "success", "data": result}), 200
