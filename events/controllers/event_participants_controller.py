"""
Training calendar participant roster for events.

Supports registered system users and walk-in guests who are not in the system.
This roster is separate from certificate assignment — use it to record attendance
first, then pull from it when issuing certificates.
"""

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from events.models.models import EventParticipant
from events.models.schemas import EventParticipantBulkInput, EventParticipantUpdateInput
from events.services.event_participant_service import (
    build_participant_view,
    create_participant_row,
    existing_guest_keys,
    existing_user_ids,
    get_event_or_error,
    get_salutation_or_error,
    list_event_participants,
    validate_email,
)
from database.db_connector import get_db

event_participants_bp = Blueprint("event_participants", __name__)


@event_participants_bp.route("/api/events/<int:event_id>/participants", methods=["GET"])
@jwt_required()
def list_participants(event_id: int):
    """
    List attendance roster for a training calendar event.

    Query params:
      - participant_type: user | walk_in (optional filter)
    """
    db = get_db()
    try:
        _, error = get_event_or_error(db, event_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        participant_type = (request.args.get("participant_type") or "").strip().lower() or None
        if participant_type and participant_type not in {"user", "walk_in"}:
            return jsonify({
                "status": "error",
                "message": "participant_type must be 'user' or 'walk_in'",
            }), 400

        participants = list_event_participants(db, event_id, participant_type=participant_type)
        walk_in_count = sum(1 for item in participants if item["participant_type"] == "walk_in")
        user_count = len(participants) - walk_in_count

        return jsonify({
            "status": "success",
            "data": {
                "event_id": event_id,
                "total": len(participants),
                "walk_in_count": walk_in_count,
                "user_count": user_count,
                "participants": participants,
            },
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@event_participants_bp.route("/api/events/<int:event_id>/participants", methods=["POST"])
@jwt_required()
def add_participants(event_id: int):
    """
    Bulk add participants to a training calendar event.

    Each entry is either a system user or a walk-in guest:

    {
      "participants": [
        { "user_id": 42 },
        {
          "full_name": "John Doe",
          "salutation_id": 4,
          "organization": "ACME Ltd",
          "email": "john@example.com"
        }
      ]
    }
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        _, error = get_event_or_error(db, event_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        body = request.get_json(silent=True) or {}
        try:
            parsed = EventParticipantBulkInput(**body)
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        seen_user_ids = existing_user_ids(db, event_id)
        seen_guest_keys = existing_guest_keys(db, event_id)
        created = []

        for item in parsed.participants:
            row, row_error = create_participant_row(
                db,
                event_id,
                item.model_dump(),
                current_user_id,
                seen_user_ids=seen_user_ids,
                seen_guest_keys=seen_guest_keys,
            )
            if row_error:
                return jsonify({"status": "error", "message": row_error}), 400
            db.add(row)
            created.append(row)

        db.commit()

        return jsonify({
            "status": "success",
            "message": f"{len(created)} participant(s) added",
            "data": {
                "event_id": event_id,
                "participants": [build_participant_view(db, row) for row in created],
            },
        }), 201
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@event_participants_bp.route(
    "/api/events/<int:event_id>/participants/<int:participant_id>",
    methods=["PATCH"],
)
@jwt_required()
def update_participant(event_id: int, participant_id: int):
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        _, error = get_event_or_error(db, event_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        row = (
            db.query(EventParticipant)
            .filter(
                EventParticipant.id == participant_id,
                EventParticipant.event_id == event_id,
                EventParticipant.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Participant not found"}), 404

        body = request.get_json(silent=True) or {}
        try:
            parsed = EventParticipantUpdateInput(**body)
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        updates = parsed.model_dump(exclude_unset=True)
        if not updates:
            return jsonify({"status": "error", "message": "No fields to update"}), 400

        if row.user_id is not None and "full_name" in updates:
            return jsonify({
                "status": "error",
                "message": "full_name cannot be updated for system users",
            }), 400
        if row.user_id is not None and "salutation_id" in updates:
            return jsonify({
                "status": "error",
                "message": "salutation_id cannot be updated for system users",
            }), 400

        if "email" in updates:
            email_error = validate_email(updates.get("email"))
            if email_error:
                return jsonify({"status": "error", "message": email_error}), 400

        if "salutation_id" in updates and updates["salutation_id"] is not None:
            _, salutation_error = get_salutation_or_error(db, updates["salutation_id"])
            if salutation_error:
                return jsonify({"status": "error", "message": salutation_error}), 400

        for field, value in updates.items():
            if field in {"organization", "email", "phone", "notes"}:
                value = (value or "").strip() or None if value is not None else None
            setattr(row, field, value)
        row.updated_by = current_user_id

        db.commit()
        return jsonify({
            "status": "success",
            "message": "Participant updated successfully",
            "data": build_participant_view(db, row),
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@event_participants_bp.route(
    "/api/events/<int:event_id>/participants/<int:participant_id>",
    methods=["DELETE"],
)
@jwt_required()
def delete_participant(event_id: int, participant_id: int):
    db = get_db()
    try:
        row = (
            db.query(EventParticipant)
            .filter(
                EventParticipant.id == participant_id,
                EventParticipant.event_id == event_id,
                EventParticipant.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Participant not found"}), 404

        row.deleted_at = datetime.utcnow()
        row.updated_by = int(get_jwt_identity())
        db.commit()
        return jsonify({
            "status": "success",
            "message": "Participant removed successfully",
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()
