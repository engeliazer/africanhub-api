"""HTTP API for starting and listing study periods."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database.db_connector import db_session
from study_access.services.access_service import StudyAccessService
from study_access.services.rules import StudyAccessError

study_access_bp = Blueprint("study_access", __name__)


def _user_id() -> int:
    return int(get_jwt_identity())


def _error(exc: StudyAccessError):
    body = {"status": "error", "message": exc.message}
    if exc.code:
        body["code"] = exc.code
    return jsonify(body), exc.status_code


@study_access_bp.route("/study-periods/start", methods=["POST"])
@jwt_required()
def start_study_period():
    data = request.get_json(silent=True) or {}
    application_id = data.get("application_id")
    subject_id = data.get("subject_id")
    if not application_id or not subject_id:
        return jsonify({
            "status": "error",
            "message": "application_id and subject_id are required",
        }), 400
    try:
        payload, status_code = StudyAccessService(db_session).start_period(
            _user_id(), int(application_id), int(subject_id)
        )
        message = "Study period started" if status_code == 201 else "Study period is already open"
        return jsonify({"status": "success", "message": message, "data": payload}), status_code
    except StudyAccessError as exc:
        db_session.rollback()
        return _error(exc)
    except Exception as exc:
        db_session.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db_session.remove()


@study_access_bp.route("/study-periods/mine", methods=["GET"])
@jwt_required()
def list_my_study_periods():
    subject_id = request.args.get("subject_id", type=int)
    try:
        periods = StudyAccessService(db_session).list_my_periods(_user_id(), subject_id)
        return jsonify({
            "status": "success",
            "message": "Study periods retrieved successfully",
            "data": {"study_periods": periods},
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db_session.remove()
