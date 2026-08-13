from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.models.models import CertificateParticipant
from certificates.models.schemas import (
    ParticipantBulkInput,
    ParticipantUpdateInput,
    participant_payload,
)
from certificates.services.event_roster_import_service import import_event_participants_to_context
from certificates.services.participant_create_service import create_certificate_participant
from certificates.services.participant_service import (
    get_salutation_for_participant,
    get_salutation_for_user,
    get_training_context_or_error,
    get_user_or_error,
    is_guest_participant,
)
from certificates.services.serial_no_service import assign_participant_serial_no
from database.db_connector import get_db

certificate_participants_bp = Blueprint("certificate_participants", __name__)


def _participant_view(db, participant, context):
    user = None
    salutation = None
    if is_guest_participant(participant):
        salutation = get_salutation_for_participant(db, participant)
    else:
        user, _ = get_user_or_error(db, participant.user_id)
        salutation = get_salutation_for_user(db, user) if user else None
    return participant_payload(participant, user, salutation, context)


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants",
    methods=["GET"],
)
@jwt_required()
def list_participants(context_id: int):
    db = get_db()
    try:
        context, error = get_training_context_or_error(db, context_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        rows = (
            db.query(CertificateParticipant)
            .filter(
                CertificateParticipant.training_context_id == context_id,
                CertificateParticipant.deleted_at.is_(None),
            )
            .order_by(CertificateParticipant.id.asc())
            .all()
        )

        participants = [_participant_view(db, row, context) for row in rows]
        participants.sort(key=lambda item: (item.get("full_name") or "").lower())

        return jsonify({
            "status": "success",
            "data": {
                "training_context_id": context_id,
                "training_type": context.training_type,
                "training_id": context.training_id,
                "training_cpd_hours": context.cpd_hours,
                "participants": participants,
            },
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants",
    methods=["POST"],
)
@jwt_required()
def add_participants(context_id: int):
    """
    Bulk add participants (Group 3).

    Event example:
      {
        "participants": [{
          "participant_id": 1,
          "type": "event",
          "event_id": 12,
          "full_name": "Jane Smith",
          "salutation_id": 7,
          "email": "jane@example.com",
          "organization": "NSSF"
        }]
      }

    Subject/course: use type + subject_id or course_id instead of event_id.
    System user shortcut: {"participants": [{"user_id": 42}]}
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        context, error = get_training_context_or_error(db, context_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        body = request.get_json(silent=True) or {}
        try:
            parsed = ParticipantBulkInput(**body)
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        created = []
        for item in parsed.participants:
            row, create_error = create_certificate_participant(
                db,
                context,
                item,
                current_user_id,
            )
            if create_error:
                status = 404 if "not found" in create_error.lower() else 400
                return jsonify({"status": "error", "message": create_error}), status
            created.append(row)

        db.commit()

        return jsonify({
            "status": "success",
            "message": f"{len(created)} participant(s) added",
            "data": {
                "training_context_id": context_id,
                "participants": [_participant_view(db, row, context) for row in created],
            },
        }), 201
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/import-event-roster",
    methods=["POST"],
)
@jwt_required()
def import_event_roster(context_id: int):
    """
    Copy training calendar attendees (event_participants) onto the certificate roster.

    Requires training_context.training_type=event. Uses context.training_id as events.id.
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        context, error = get_training_context_or_error(db, context_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        created, skipped, import_error = import_event_participants_to_context(
            db,
            context,
            current_user_id,
        )
        if import_error:
            return jsonify({"status": "error", "message": import_error}), 400

        db.commit()

        return jsonify({
            "status": "success",
            "message": f"{len(created)} participant(s) imported, {skipped} skipped",
            "data": {
                "training_context_id": context_id,
                "event_id": context.training_id,
                "imported_count": len(created),
                "skipped_count": skipped,
                "participants": [_participant_view(db, row, context) for row in created],
            },
        }), 201
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>",
    methods=["PATCH"],
)
@jwt_required()
def update_participant(context_id: int, participant_id: int):
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        context, error = get_training_context_or_error(db, context_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        row = (
            db.query(CertificateParticipant)
            .filter(
                CertificateParticipant.id == participant_id,
                CertificateParticipant.training_context_id == context_id,
                CertificateParticipant.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Participant not found"}), 404

        body = request.get_json(silent=True) or {}
        try:
            parsed = ParticipantUpdateInput(**body)
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        updates = parsed.model_dump(exclude_unset=True)
        if not updates:
            return jsonify({"status": "error", "message": "No fields to update"}), 400

        for field, value in updates.items():
            setattr(row, field, value)
        row.updated_by = current_user_id

        if (
            updates.get("confirmation_status") == "confirmed"
            and not row.serial_no
        ):
            assign_participant_serial_no(db, row, context)

        db.commit()

        return jsonify({
            "status": "success",
            "message": "Participant updated successfully",
            "data": _participant_view(db, row, context),
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>",
    methods=["DELETE"],
)
@jwt_required()
def delete_participant(context_id: int, participant_id: int):
    db = get_db()
    try:
        row = (
            db.query(CertificateParticipant)
            .filter(
                CertificateParticipant.id == participant_id,
                CertificateParticipant.training_context_id == context_id,
                CertificateParticipant.deleted_at.is_(None),
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
