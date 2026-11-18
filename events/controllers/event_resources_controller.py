"""
Event learning resources (zip packs).

Admin uploads packs while registering an event. Attendees list and download them
with the same attendance number (certificate serial_no) used for certificates.
"""

import logging
import os

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from database.db_connector import get_db
from events.models.models import Event
from events.services.event_resource_service import (
    absolute_resource_path,
    attendance_number_from_request,
    create_event_resource,
    get_active_resource,
    list_active_resources,
    resolve_event_by_attendance_number,
    resource_download_name,
    resource_to_dict,
    soft_delete_event_resource,
)

logger = logging.getLogger(__name__)

event_resources_bp = Blueprint("event_resources", __name__)


def _get_event_or_404(db, event_id: int):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return None, (jsonify({"status": "error", "message": "Event not found"}), 404)
    return event, None


@event_resources_bp.route("/api/events/<int:event_id>/resources", methods=["GET"])
@jwt_required()
def list_event_resources(event_id: int):
    """List zip resources for an event (admin)."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        resources = list_active_resources(db, event.id)
        return jsonify({
            "status": "success",
            "data": {
                "event_id": event.id,
                "total": len(resources),
                "resources": [
                    resource_to_dict(item, include_admin_fields=True)
                    for item in resources
                ],
            },
        })
    except Exception as exc:
        logger.exception("list_event_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route("/api/events/<int:event_id>/resources", methods=["POST"])
@jwt_required()
def upload_event_resource(event_id: int):
    """
    Upload a zip resource for an event (admin).

    multipart/form-data:
      - file (required, .zip)
      - name (required)
      - description (optional)
    """
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400

        file_storage = request.files["file"]
        name = request.form.get("name")
        description = request.form.get("description")
        user_id = int(get_jwt_identity())

        resource, error = create_event_resource(
            db,
            event,
            name=name,
            description=description,
            file_storage=file_storage,
            user_id=user_id,
        )
        if error:
            return jsonify({"status": "error", "message": error}), 400

        return jsonify({
            "status": "success",
            "message": "Resource uploaded successfully",
            "data": resource_to_dict(resource, include_admin_fields=True),
        }), 201
    except Exception as exc:
        db.rollback()
        logger.exception("upload_event_resource: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route(
    "/api/events/<int:event_id>/resources/<int:resource_id>/download",
    methods=["GET"],
)
@jwt_required()
def download_event_resource_admin(event_id: int, resource_id: int):
    """Download an event zip as an admin."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        resource = get_active_resource(db, event.id, resource_id)
        if not resource:
            return jsonify({"status": "error", "message": "Resource not found"}), 404

        file_path = absolute_resource_path(resource)
        if not os.path.isfile(file_path):
            return jsonify({"status": "error", "message": "File not found"}), 404

        return send_file(
            path_or_file=file_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=resource_download_name(resource),
            conditional=True,
        )
    except Exception as exc:
        logger.exception("download_event_resource_admin: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route(
    "/api/events/<int:event_id>/resources/<int:resource_id>",
    methods=["DELETE"],
)
@jwt_required()
def delete_event_resource(event_id: int, resource_id: int):
    """Soft-delete an event resource (admin)."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        resource = get_active_resource(db, event.id, resource_id)
        if not resource:
            return jsonify({"status": "error", "message": "Resource not found"}), 404

        soft_delete_event_resource(db, resource, int(get_jwt_identity()))
        return jsonify({
            "status": "success",
            "message": "Resource deleted successfully",
        })
    except Exception as exc:
        db.rollback()
        logger.exception("delete_event_resource: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route("/api/events/public/resources", methods=["GET"])
def list_public_event_resources():
    """
    List downloadable packs for the event linked to an attendance number.

    Query: attendance_number (or serial_no). No JWT.
    """
    db = get_db()
    try:
        attendance_number = attendance_number_from_request(request.args)
        event, participant, context, participant_name, error = resolve_event_by_attendance_number(
            db,
            attendance_number,
        )
        if error:
            return jsonify({"status": "error", "message": error}), 404

        resources = list_active_resources(db, event.id)
        return jsonify({
            "status": "success",
            "data": {
                "attendance_number": participant.serial_no,
                "participant_name": participant_name,
                "event": {
                    "id": event.id,
                    "title": event.title,
                    "course_title": event.course_title,
                    "venue": event.venue,
                    "start_date": event.start_date.isoformat() if event.start_date else None,
                    "end_date": event.end_date.isoformat() if event.end_date else None,
                    "subject_title": context.subject_title if context else None,
                },
                "resource_count": len(resources),
                "resources": [
                    resource_to_dict(item, attendance_number=participant.serial_no)
                    for item in resources
                ],
            },
        })
    except Exception as exc:
        logger.exception("list_public_event_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route(
    "/api/events/public/resources/<int:resource_id>/download",
    methods=["GET"],
)
def download_public_event_resource(resource_id: int):
    """
    Download one event zip using an attendance number.

    Query: attendance_number (or serial_no). No JWT.
    """
    db = get_db()
    try:
        attendance_number = attendance_number_from_request(request.args)
        event, _participant, _context, _name, error = resolve_event_by_attendance_number(
            db,
            attendance_number,
        )
        if error:
            return jsonify({"status": "error", "message": error}), 404

        resource = get_active_resource(db, event.id, resource_id)
        if not resource:
            return jsonify({"status": "error", "message": "Resource not found"}), 404

        file_path = absolute_resource_path(resource)
        if not os.path.isfile(file_path):
            return jsonify({"status": "error", "message": "File not found"}), 404

        return send_file(
            path_or_file=file_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=resource_download_name(resource),
            conditional=True,
        )
    except Exception as exc:
        logger.exception("download_public_event_resource: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()

