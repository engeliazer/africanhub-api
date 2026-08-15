from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.models.models import CertificateParticipant
from certificates.models.schemas import (
    ParticipantBulkInput,
    ParticipantNotifyAttendanceInput,
    ParticipantUpdateInput,
    participant_payload,
)
from certificates.services.certificate_issue_service import (
    get_participant_certificate,
    issue_certificate_for_participant,
)
from certificates.services.event_roster_import_service import import_event_participants_to_context
from certificates.services.participant_create_service import create_certificate_participant
from certificates.services.participant_service import (
    get_salutation_by_id,
    get_salutation_for_participant,
    get_salutation_for_user,
    get_training_context_or_error,
    get_user_or_error,
    is_guest_participant,
)
from certificates.services.participant_attendance_notify_service import (
    notify_context_participants_attendance,
    notify_single_participant_attendance,
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
            _, _, issue_error = issue_certificate_for_participant(
                db,
                context,
                row,
                current_user_id,
            )
            if issue_error:
                db.rollback()
                return jsonify({"status": "error", "message": issue_error}), 400
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

        for row in created:
            _, _, issue_error = issue_certificate_for_participant(
                db,
                context,
                row,
                current_user_id,
            )
            if issue_error:
                db.rollback()
                return jsonify({"status": "error", "message": issue_error}), 400

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
    "/certificate-training-contexts/<int:context_id>/participants/notify-attendance",
    methods=["POST"],
)
@jwt_required()
def notify_participants_attendance(context_id: int):
    """
    SMS thank-you with each participant's attendance number (serial_no).

    Optional body: { "participant_ids": [1, 2] } — omit to notify all roster rows.
    """
    db = get_db()
    try:
        context, error = get_training_context_or_error(db, context_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        body = request.get_json(silent=True) or {}
        try:
            parsed = ParticipantNotifyAttendanceInput(**body)
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        results, counts = notify_context_participants_attendance(
            db,
            context,
            participant_ids=parsed.participant_ids,
        )

        db.commit()

        sent = counts.get("sent", 0)
        skipped = counts.get("skipped", 0)
        failed = counts.get("failed", 0)
        return jsonify({
            "status": "success",
            "message": (
                f"{sent} notification(s) sent, {skipped} skipped, {failed} failed"
            ),
            "data": {
                "training_context_id": context_id,
                "sent_count": sent,
                "skipped_count": skipped,
                "failed_count": failed,
                "results": results,
            },
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>/notify-attendance",
    methods=["POST"],
)
@jwt_required()
def notify_participant_attendance(context_id: int, participant_id: int):
    """SMS thank-you with attendance number (serial_no) for one roster participant."""
    db = get_db()
    try:
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

        result = notify_single_participant_attendance(db, context, row)
        db.commit()

        outcome_messages = {
            "sent": "Attendance notification sent",
            "skipped": result.get("reason", "Notification skipped"),
            "failed": result.get("reason", "Failed to send notification"),
        }

        return jsonify({
            "status": "success" if result["status"] == "sent" else "error",
            "message": outcome_messages.get(result["status"], "Notification processed"),
            "data": result,
        }), 200 if result["status"] == "sent" else 400
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_participants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>",
    methods=["PATCH"],
)
@jwt_required()
def update_participant(context_id: int, participant_id: int):
    """
    Update a certificate roster participant.

    Name corrections:
      - full_name — guest participants only (user_id is null)
      - salutation_id — guest row or linked user's salutation

    Also supports confirmation_status and qualifies_for_cpd_override.
    Regenerates the certificate PDF when the name or salutation changes.
    """
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

        name_updated = False

        if "full_name" in updates:
            if not is_guest_participant(row):
                return jsonify({
                    "status": "error",
                    "message": (
                        "full_name can only be updated for guest participants. "
                        "Update the linked user profile for system users."
                    ),
                }), 400
            row.full_name = updates["full_name"]
            name_updated = True

        if "salutation_id" in updates:
            salutation_id = updates["salutation_id"]
            if salutation_id is not None and not get_salutation_by_id(db, salutation_id):
                return jsonify({
                    "status": "error",
                    "message": f"Salutation {salutation_id} not found or inactive",
                }), 404
            if is_guest_participant(row):
                row.salutation_id = salutation_id
            else:
                user, user_error = get_user_or_error(db, row.user_id)
                if user_error:
                    return jsonify({"status": "error", "message": user_error}), 404
                user.salutation_id = salutation_id
            name_updated = True

        for field in ("qualifies_for_cpd_override", "confirmation_status"):
            if field in updates:
                setattr(row, field, updates[field])

        row.updated_by = current_user_id

        if (
            updates.get("confirmation_status") == "confirmed"
            and not row.serial_no
        ):
            assign_participant_serial_no(db, row, context)

        if name_updated and (row.confirmation_status or "").strip().lower() == "confirmed":
            existing_certificate = get_participant_certificate(db, row)
            _, _, issue_error = issue_certificate_for_participant(
                db,
                context,
                row,
                current_user_id,
                regenerate=existing_certificate is not None,
            )
            if issue_error:
                db.rollback()
                return jsonify({"status": "error", "message": issue_error}), 400
        elif row.confirmation_status == "confirmed" and not row.certificate_id:
            _, _, issue_error = issue_certificate_for_participant(
                db,
                context,
                row,
                current_user_id,
            )
            if issue_error:
                db.rollback()
                return jsonify({"status": "error", "message": issue_error}), 400

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
