from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.models.schemas import participant_payload
from certificates.services.applicant_service import (
    build_applicants_response,
    fetch_approved_applicants_for_subject,
    get_subject_or_error,
    parse_optional_bool,
    roster_user_ids,
)
from certificates.services.participant_service import (
    get_salutation_for_user,
    get_training_context_or_error,
    get_user_or_error,
)
from database.db_connector import get_db

certificate_applicants_bp = Blueprint("certificate_applicants", __name__)


def _participant_view(db, participant, context):
    user, _ = get_user_or_error(db, participant.user_id)
    salutation = get_salutation_for_user(db, user) if user else None
    return participant_payload(participant, user, salutation, context)


@certificate_applicants_bp.route(
    "/subjects/<int:subject_id>/approved-certificate-applicants",
    methods=["GET"],
)
@jwt_required()
def list_approved_certificate_applicants(subject_id: int):
    """
    List approved applicants for a subject — use to prepare certificate participants.

    Query params:
      - training_context_id (required when using assignment filters)
      - pending_certificate_assignment=true  → not yet on this context roster
      - pending_certificate_assignment=false → already on this context roster
      - missing_salutation=true              → users without users.salutation_id
      - missing_salutation=false             → users with salutation set
    """
    db = get_db()
    try:
        subject, error = get_subject_or_error(db, subject_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        try:
            pending_certificate_assignment = parse_optional_bool(
                request.args.get("pending_certificate_assignment")
            )
            missing_salutation = parse_optional_bool(request.args.get("missing_salutation"))
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        training_context_id = request.args.get("training_context_id", type=int)

        if pending_certificate_assignment is not None and not training_context_id:
            return jsonify({
                "status": "error",
                "message": "training_context_id is required when pending_certificate_assignment is set",
            }), 400

        if training_context_id:
            _, context_error = get_training_context_or_error(db, training_context_id)
            if context_error:
                return jsonify({"status": "error", "message": context_error}), 404

            context_row = (
                db.query(CertificateTrainingContext)
                .filter(
                    CertificateTrainingContext.id == training_context_id,
                    CertificateTrainingContext.deleted_at.is_(None),
                )
                .first()
            )
            if (
                context_row.training_type != "subject"
                or context_row.training_id != subject_id
            ):
                return jsonify({
                    "status": "error",
                    "message": "training_context_id does not match this subject",
                }), 400

        rows = fetch_approved_applicants_for_subject(db, subject_id)
        data = build_applicants_response(
            db,
            subject,
            rows,
            training_context_id=training_context_id,
            pending_certificate_assignment=pending_certificate_assignment,
            missing_salutation=missing_salutation,
        )

        return jsonify({"status": "success", "data": data})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_applicants_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/import-approved-applicants",
    methods=["POST"],
)
@jwt_required()
def import_approved_applicants(context_id: int):
    """
    Add all approved applicants for a subject onto the certificate roster.

    Body (optional if context is already linked to a subject):
    {
      "subject_id": 12
    }
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        context, error = get_training_context_or_error(db, context_id)
        if error:
            return jsonify({"status": "error", "message": error}), 404

        body = request.get_json(silent=True) or {}
        subject_id = body.get("subject_id")

        if subject_id is None:
            if context.training_type != "subject":
                return jsonify({
                    "status": "error",
                    "message": "subject_id is required when training context is not linked to a subject",
                }), 400
            subject_id = context.training_id
        else:
            subject_id = int(subject_id)
            if context.training_type == "subject" and context.training_id != subject_id:
                return jsonify({
                    "status": "error",
                    "message": "subject_id does not match this training context",
                }), 400

        subject, subject_error = get_subject_or_error(db, subject_id)
        if subject_error:
            return jsonify({"status": "error", "message": subject_error}), 404

        rows = fetch_approved_applicants_for_subject(db, subject_id)
        existing = roster_user_ids(db, context_id)

        created = []
        skipped = 0
        seen_user_ids = set()

        for _detail, _application, user in rows:
            if user.id in seen_user_ids:
                continue
            seen_user_ids.add(user.id)

            if user.id in existing:
                skipped += 1
                continue

            row = CertificateParticipant(
                training_context_id=context_id,
                user_id=user.id,
                created_by=current_user_id,
                updated_by=current_user_id,
            )
            db.add(row)
            created.append(row)

        db.commit()

        return jsonify({
            "status": "success",
            "message": f"{len(created)} participant(s) imported, {skipped} skipped (already on roster)",
            "data": {
                "training_context_id": context_id,
                "subject_id": subject_id,
                "subject_name": subject.name,
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
