"""
Event learning resources (zip packs).

Admin uploads packs while registering an event. Attendees list and download them
with the same attendance number (certificate serial_no) used for certificates.
"""

import html
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import API_BASE_URL, PUBLIC_WEBSITE_URL
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

SHARE_LINK_TTL_SECONDS = 60 * 60


def _share_serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("FILE_ACCESS_SECRET") or os.getenv("JWT_SECRET_KEY") or "event-resource-share"
    return URLSafeTimedSerializer(secret, salt="event-resource-share")


def make_share_token(event_id: int) -> str:
    return _share_serializer().dumps({"event_id": int(event_id)})


def share_token_status(token: str, event_id: int) -> str:
    """Return 'ok', 'expired', or 'invalid'."""
    if not token:
        return "invalid"
    try:
        data = _share_serializer().loads(token, max_age=SHARE_LINK_TTL_SECONDS)
    except SignatureExpired:
        return "expired"
    except BadSignature:
        return "invalid"
    try:
        token_event_id = int(data.get("event_id"))
    except (TypeError, ValueError):
        return "invalid"
    if token_event_id != int(event_id):
        return "invalid"
    return "ok"


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


def _learning_resources_payload(event_id: int, resources) -> dict:
    latest = resources[-1] if resources else None
    filename = None
    if latest is not None:
        filename = getattr(latest, "original_filename", None) or latest.name
    return {
        "event_id": event_id,
        "has_learning_resources": bool(resources),
        "learning_resources_filename": filename,
        "learning_resources_name": latest.name if latest else None,
        "learning_resources_url": (
            f"/api/events/{event_id}/learning-resources/download" if latest else None
        ),
        "resource_count": len(resources),
    }


@event_resources_bp.route("/api/events/<int:event_id>/learning-resources", methods=["GET"])
@jwt_required()
def get_learning_resources(event_id: int):
    """Single-zip view used by the admin calendar."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response
        resources = list_active_resources(db, event.id)
        return jsonify({
            "status": "success",
            "data": _learning_resources_payload(event.id, resources),
        })
    except Exception as exc:
        logger.exception("get_learning_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route("/api/events/<int:event_id>/learning-resources", methods=["POST"])
@jwt_required()
def upload_learning_resources(event_id: int):
    """Replace the event zip. Accepts the admin field name learning_resources."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        upload = request.files.get("learning_resources") or request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"status": "error", "message": "A zip file is required"}), 400

        name = (request.form.get("name") or "").strip()
        if not name:
            name = os.path.splitext(upload.filename)[0] or "Learning resources"

        resource, error = create_event_resource(
            db,
            event,
            name=name,
            description=(request.form.get("description") or "").strip() or None,
            file_storage=upload,
            user_id=int(get_jwt_identity()),
        )
        if error:
            return jsonify({"status": "error", "message": error}), 400

        for existing in list_active_resources(db, event.id):
            if existing.id != resource.id:
                soft_delete_event_resource(db, existing, int(get_jwt_identity()))

        return jsonify({
            "status": "success",
            "data": _learning_resources_payload(event.id, [resource]),
        }), 201
    except Exception as exc:
        logger.exception("upload_learning_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route(
    "/api/events/<int:event_id>/learning-resources/download",
    methods=["GET"],
)
@jwt_required()
def download_learning_resources(event_id: int):
    """Download the current event zip."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        resources = list_active_resources(db, event.id)
        if not resources:
            return jsonify({"status": "error", "message": "Learning resources not found"}), 404

        resource = resources[-1]
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
        logger.exception("download_learning_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route("/api/events/<int:event_id>/learning-resources", methods=["DELETE"])
@jwt_required()
def delete_learning_resources(event_id: int):
    """Remove every zip attached to the event."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response

        user_id = int(get_jwt_identity())
        for resource in list_active_resources(db, event.id):
            soft_delete_event_resource(db, resource, user_id)

        return jsonify({
            "status": "success",
            "data": _learning_resources_payload(event.id, []),
        })
    except Exception as exc:
        logger.exception("delete_learning_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


def public_resources_url(event_id: int) -> str:
    return f"{API_BASE_URL}/api/events/public/{event_id}/resources"


def public_resource_download_url(event_id: int, resource_id: int, token: str) -> str:
    return (
        f"{public_resources_url(event_id)}/{resource_id}/download"
        f"?token={quote(token, safe='')}"
    )


def _share_link(event_id: int, token: str) -> str:
    return (
        f"{PUBLIC_WEBSITE_URL}/learning-resources/{int(event_id)}"
        f"?token={quote(token, safe='')}"
    )


def _public_resources_payload(event, resources, token: str) -> dict:
    subject_name = event.course_title
    return {
        "public_url": _share_link(event.id, token),
        "event": {
            "id": event.id,
            "title": event.title,
            "course_title": event.course_title,
            "subject_name": subject_name,
            "venue": event.venue,
            "start_date": event.start_date.isoformat() if event.start_date else None,
            "end_date": event.end_date.isoformat() if event.end_date else None,
            "start_time": event.start_time.isoformat(timespec="minutes") if getattr(event, "start_time", None) else None,
            "end_time": event.end_time.isoformat(timespec="minutes") if getattr(event, "end_time", None) else None,
        },
        "resource_count": len(resources),
        "resources": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "file_size": item.file_size,
                "download_url": public_resource_download_url(event.id, item.id, token),
            }
            for item in resources
        ],
    }


def _wants_json() -> bool:
    if request.args.get("format") == "json":
        return True
    if request.args.get("format") == "html":
        return False
    best = request.accept_mimetypes.best_match(["text/html", "application/json"])
    return best == "application/json"


def _public_resources_page(event, resources, token: str) -> str:
    subject = html.escape(event.course_title or event.title or "Course")
    title = html.escape(event.title or "")
    start = event.start_date.isoformat() if event.start_date else ""
    end = event.end_date.isoformat() if event.end_date else ""
    if start and end:
        dates = html.escape(f"{start} to {end}")
    else:
        dates = html.escape(start or end)
    venue = html.escape(event.venue or "")
    rows = []
    for item in resources:
        name = html.escape(item.name or "Resource")
        description = html.escape(item.description or "")
        href = html.escape(
            f"/api/events/public/{event.id}/resources/{item.id}/download?token={quote(token, safe='')}"
        )
        detail = f"<p>{description}</p>" if description else ""
        rows.append(
            f"<li><h2>{name}</h2>{detail}"
            f"<a href=\"{href}\">Download</a></li>"
        )
    resource_html = "".join(rows) or "<li>No resources have been added yet.</li>"
    heading = title if title and title != subject else subject
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{heading}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 0; background: #f6f3ee; color: #1c1915; }}
    main {{ max-width: 40rem; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }}
    h1 {{ font-size: 2rem; line-height: 1.2; margin-bottom: 0.4rem; }}
    .meta {{ color: #5c564e; margin: 0 0 1.5rem; }}
    ul {{ list-style: none; padding: 0; margin: 0; }}
    li {{ background: #fff; border: 1px solid #e4ddd2; border-radius: 8px; padding: 1rem 1.1rem; margin-bottom: 0.75rem; }}
    h2 {{ font-size: 1.15rem; margin: 0 0 0.35rem; }}
    a {{ display: inline-block; margin-top: 0.6rem; background: #8c3a1e; color: #fff; text-decoration: none; padding: 0.45rem 0.8rem; border-radius: 6px; }}
  </style>
</head>
<body>
  <main>
    <h1>{heading}</h1>
    <p class="meta">{subject}<br>{dates}<br>{venue}</p>
    <ul>{resource_html}</ul>
  </main>
</body>
</html>"""


def _share_failure(status: str):
    if status == "expired":
        message = "This link has expired. It is only valid for 60 minutes."
    else:
        message = "This link is not valid."
    if _wants_json():
        return jsonify({"status": "error", "message": message}), 403
    page = (
        "<!DOCTYPE html><html><body><p>"
        + html.escape(message)
        + "</p></body></html>"
    )
    return Response(page, status=403, mimetype="text/html")


@event_resources_bp.route("/api/events/<int:event_id>/resources/share-link", methods=["POST"])
@jwt_required()
def create_resource_share_link(event_id: int):
    """Issue a public resources link that expires after 60 minutes."""
    db = get_db()
    try:
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response
        token = make_share_token(event.id)
        expires_at = datetime.utcnow() + timedelta(seconds=SHARE_LINK_TTL_SECONDS)
        return jsonify({
            "status": "success",
            "data": {
                "url": _share_link(event.id, token),
                "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expires_in_seconds": SHARE_LINK_TTL_SECONDS,
            },
        })
    except Exception as exc:
        logger.exception("create_resource_share_link: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route("/api/events/public/<int:event_id>/resources", methods=["GET"])
def public_event_resources(event_id: int):
    """Public page for a time-limited share link. No login."""
    db = get_db()
    try:
        status = share_token_status(request.args.get("token", ""), event_id)
        if status != "ok":
            return _share_failure(status)
        event, error_response = _get_event_or_404(db, event_id)
        if error_response:
            return error_response
        token = request.args.get("token", "")
        resources = list_active_resources(db, event.id)
        if _wants_json():
            return jsonify({
                "status": "success",
                "data": _public_resources_payload(event, resources, token),
            })
        return Response(_public_resources_page(event, resources, token), mimetype="text/html")
    except Exception as exc:
        logger.exception("public_event_resources: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_resources_bp.route(
    "/api/events/public/<int:event_id>/resources/<int:resource_id>/download",
    methods=["GET"],
)
def download_public_event_resource_by_event(event_id: int, resource_id: int):
    """Download one zip using the same 60-minute share link. No login."""
    db = get_db()
    try:
        status = share_token_status(request.args.get("token", ""), event_id)
        if status != "ok":
            return _share_failure(status)
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
        logger.exception("download_public_event_resource_by_event: %s", exc)
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

