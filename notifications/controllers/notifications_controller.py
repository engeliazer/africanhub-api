from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from database.db_connector import get_db
from notifications.models.models import PublicNotification, PublicNotificationRead

notifications_bp = Blueprint("notifications", __name__)


def _parse_datetime(value, field):
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an ISO 8601 datetime")


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _notification_dict(row):
    return {
        "id": row.id,
        "title": row.title,
        "message": row.message,
        "type": row.notification_type,
        "link": row.link,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "is_published": bool(row.is_published),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _apply_payload(row, data, *, creating=False):
    title = data.get("title", row.title)
    message = data.get("message", row.message)
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title is required")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message is required")
    row.title = title.strip()
    row.message = message.strip()

    if "type" in data or creating:
        kind = data.get("type", "general")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("type must be a non-empty string")
        row.notification_type = kind.strip()[:50]
    if "link" in data or creating:
        link = data.get("link")
        row.link = link.strip() if isinstance(link, str) and link.strip() else None
        if row.link and len(row.link) > 1000:
            raise ValueError("link must be 1000 characters or fewer")
    if "starts_at" in data or creating:
        row.starts_at = _parse_datetime(data.get("starts_at"), "starts_at")
    if "expires_at" in data or creating:
        row.expires_at = _parse_datetime(data.get("expires_at"), "expires_at")
    if row.starts_at and row.expires_at and row.expires_at <= row.starts_at:
        raise ValueError("expires_at must be later than starts_at")
    if "is_published" in data or creating:
        row.is_published = _parse_bool(data.get("is_published"), False)


@notifications_bp.route("/api/notifications", methods=["GET"])
@jwt_required()
def list_notifications():
    db = get_db()
    try:
        rows = db.query(PublicNotification).order_by(PublicNotification.created_at.desc()).all()
        return jsonify({"status": "success", "data": [_notification_dict(row) for row in rows]})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@notifications_bp.route("/api/notifications", methods=["POST"])
@jwt_required()
def create_notification():
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        row = PublicNotification(created_by=user_id, updated_by=user_id)
        _apply_payload(row, data, creating=True)
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({"status": "success", "message": "Notification created", "data": _notification_dict(row)}), 201
    except ValueError as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@notifications_bp.route("/api/notifications/<int:notification_id>", methods=["PUT"])
@jwt_required()
def update_notification(notification_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        row = db.query(PublicNotification).filter(PublicNotification.id == notification_id).first()
        if not row:
            return jsonify({"status": "error", "message": "Notification not found"}), 404
        _apply_payload(row, data)
        row.updated_by = int(get_jwt_identity())
        db.commit()
        db.refresh(row)
        return jsonify({"status": "success", "message": "Notification updated", "data": _notification_dict(row)})
    except ValueError as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@notifications_bp.route("/api/notifications/<int:notification_id>", methods=["DELETE"])
@jwt_required()
def delete_notification(notification_id):
    db = get_db()
    try:
        row = db.query(PublicNotification).filter(PublicNotification.id == notification_id).first()
        if not row:
            return jsonify({"status": "error", "message": "Notification not found"}), 404
        db.delete(row)
        db.commit()
        return jsonify({"status": "success", "message": "Notification deleted"})
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@notifications_bp.route("/api/notifications/public", methods=["GET"])
def list_public_notifications():
    visitor_id = (request.args.get("visitor_id") or "").strip()
    if not visitor_id or len(visitor_id) > 255:
        return jsonify({"status": "error", "message": "visitor_id is required and must be 255 characters or fewer"}), 400
    db = get_db()
    try:
        now = datetime.utcnow()
        read_ids = db.query(PublicNotificationRead.notification_id).filter(
            PublicNotificationRead.visitor_id == visitor_id
        )
        rows = (
            db.query(PublicNotification)
            .filter(
                PublicNotification.is_published.is_(True),
                or_(PublicNotification.starts_at.is_(None), PublicNotification.starts_at <= now),
                or_(PublicNotification.expires_at.is_(None), PublicNotification.expires_at > now),
                ~PublicNotification.id.in_(read_ids),
            )
            .order_by(PublicNotification.created_at.desc(), PublicNotification.id.desc())
            .all()
        )
        return jsonify({"status": "success", "data": [_notification_dict(row) for row in rows]})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@notifications_bp.route("/api/notifications/public/<int:notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id):
    data = request.get_json(silent=True) or {}
    visitor_id = (data.get("visitor_id") or request.args.get("visitor_id") or "").strip()
    if not visitor_id or len(visitor_id) > 255:
        return jsonify({"status": "error", "message": "visitor_id is required and must be 255 characters or fewer"}), 400
    db = get_db()
    try:
        row = db.query(PublicNotification).filter(
            PublicNotification.id == notification_id,
            PublicNotification.is_published.is_(True),
        ).first()
        if not row:
            return jsonify({"status": "error", "message": "Notification not found"}), 404
        already_read = db.query(PublicNotificationRead.id).filter(
            PublicNotificationRead.notification_id == notification_id,
            PublicNotificationRead.visitor_id == visitor_id,
        ).first()
        if not already_read:
            db.add(PublicNotificationRead(notification_id=notification_id, visitor_id=visitor_id))
            db.commit()
        return jsonify({"status": "success", "message": "Notification marked as read"})
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()
