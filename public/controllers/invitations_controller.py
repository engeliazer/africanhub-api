"""
Invitation campaign management — Phase 1: trainers + invitation CRUD.
"""

import logging
import re
from datetime import datetime, time as time_type
from decimal import Decimal
from typing import Any, Dict, List, Optional

from io import BytesIO
from pathlib import Path

from flask import Blueprint, request, jsonify, send_file, Response
from flask_jwt_extended import get_jwt_identity, jwt_required

from applications.models.models import (
    Invitation,
    InvitationCampaignStatus,
    InvitationInvitee,
    InvitationTrainer,
    InvitationTrainerAssignment,
    InviteeSendStatus,
    InviteeValidationStatus,
)
from database.db_connector import get_db
from public.controllers.invitation_trainer_photo_utils import (
    handle_invitation_trainer_photo_upload,
)
from public.services.invitation_invitee_service import (
    build_invitee_summary,
    sync_invitation_invitees,
    validate_invitee_rows,
)
from public.services.invitation_html_service import (
    build_invitation_render_context,
    invitee_dict_from_model,
    render_invitation_html,
    sample_invitee_dict,
)
from public.services.invitation_campaign_pdf_service import (
    render_invitation_pdf_bytes,
    render_sample_invitation_pdf,
)
from public.services.invitation_campaign_template_service import (
    delete_campaign_template_file,
    save_campaign_template,
    validate_campaign_template_upload,
)
from public.services.invitation_campaign_send_service import (
    count_pending_valid_invitees,
    send_test_invitation_email,
)
from public.services.invitation_campaign_processor import (
    queue_invitation_campaign_processing,
)

logger = logging.getLogger(__name__)

invitations_bp = Blueprint("invitations", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_date(value: str, field: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    raise ValueError(f"{field} must be YYYY-MM-DD")


def _parse_time(value: str, field: str) -> time_type:
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except (ValueError, AttributeError):
            continue
    raise ValueError(f"{field} must be HH:MM or HH:MM:SS")


def _parse_datetime_optional(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("scheduled_at must be ISO datetime")


def _decimal_optional(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _trainer_to_dict(trainer: InvitationTrainer) -> Dict[str, Any]:
    return {
        "id": trainer.id,
        "full_name": trainer.full_name,
        "designation": trainer.designation,
        "bio": trainer.bio,
        "qualifications": trainer.qualifications,
        "photo": trainer.photo,
        "is_active": trainer.is_active,
        "created_by": trainer.created_by,
        "updated_by": trainer.updated_by,
        "created_at": trainer.created_at.isoformat() if trainer.created_at else None,
        "updated_at": trainer.updated_at.isoformat() if trainer.updated_at else None,
    }


def _invitee_to_dict(invitee: InvitationInvitee) -> Dict[str, Any]:
    return {
        "id": invitee.id,
        "full_name": invitee.full_name,
        "email": invitee.email,
        "address": invitee.address,
        "organization": invitee.organization,
        "validation_status": invitee.validation_status.value if invitee.validation_status else None,
        "validation_message": invitee.validation_message,
        "send_status": invitee.send_status.value if invitee.send_status else None,
        "error_message": invitee.error_message,
        "sent_at": invitee.sent_at.isoformat() if invitee.sent_at else None,
        "processed_at": invitee.processed_at.isoformat() if invitee.processed_at else None,
        "created_at": invitee.created_at.isoformat() if invitee.created_at else None,
    }


def _invitation_to_dict(
    invitation: Invitation,
    *,
    include_trainers: bool = True,
    include_invitees: bool = False,
) -> Dict[str, Any]:
    trainers = []
    if include_trainers:
        ordered = sorted(
            invitation.trainer_assignments,
            key=lambda a: (a.display_order, a.id),
        )
        for assignment in ordered:
            if assignment.trainer:
                item = _trainer_to_dict(assignment.trainer)
                item["display_order"] = assignment.display_order
                item["assignment_id"] = assignment.id
                trainers.append(item)

    invitee_counts = {
        "total": len(invitation.invitees),
        "valid": sum(
            1 for i in invitation.invitees
            if i.validation_status == InviteeValidationStatus.valid
        ),
        "invalid": sum(
            1 for i in invitation.invitees
            if i.validation_status == InviteeValidationStatus.invalid
        ),
        "duplicate": sum(
            1 for i in invitation.invitees
            if i.validation_status == InviteeValidationStatus.duplicate
        ),
        "pending_send": sum(
            1 for i in invitation.invitees
            if i.send_status == InviteeSendStatus.pending
        ),
        "sent": sum(
            1 for i in invitation.invitees
            if i.send_status == InviteeSendStatus.sent
        ),
        "failed": sum(
            1 for i in invitation.invitees
            if i.send_status == InviteeSendStatus.failed
        ),
    }

    data: Dict[str, Any] = {
        "id": invitation.id,
        "title": invitation.title,
        "course_title": invitation.course_title,
        "course_description": invitation.course_description,
        "venue": invitation.venue,
        "start_date": invitation.start_date.isoformat() if invitation.start_date else None,
        "end_date": invitation.end_date.isoformat() if invitation.end_date else None,
        "start_time": invitation.start_time.strftime("%H:%M:%S") if invitation.start_time else None,
        "end_time": invitation.end_time.strftime("%H:%M:%S") if invitation.end_time else None,
        "learning_outcomes": invitation.learning_outcomes,
        "source_email": invitation.source_email,
        "email_subject": invitation.email_subject,
        "email_message": invitation.email_message,
        "course_fee": float(invitation.course_fee) if invitation.course_fee is not None else None,
        "deposit_amount": float(invitation.deposit_amount) if invitation.deposit_amount is not None else None,
        "reservation_deadline": (
            invitation.reservation_deadline.isoformat()
            if invitation.reservation_deadline else None
        ),
        "bank_account_name": invitation.bank_account_name,
        "bank_account_number": invitation.bank_account_number,
        "bank_name": invitation.bank_name,
        "interval_seconds": invitation.interval_seconds,
        "interval_limit": invitation.interval_limit,
        "scheduled_at": invitation.scheduled_at.isoformat() if invitation.scheduled_at else None,
        "has_template": bool(invitation.invitation_template_path),
        "invitation_template_filename": invitation.invitation_template_filename,
        "status": invitation.status.value if invitation.status else None,
        "started_at": invitation.started_at.isoformat() if invitation.started_at else None,
        "completed_at": invitation.completed_at.isoformat() if invitation.completed_at else None,
        "created_by": invitation.created_by,
        "updated_by": invitation.updated_by,
        "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
        "updated_at": invitation.updated_at.isoformat() if invitation.updated_at else None,
        "trainers": trainers,
        "invitee_counts": invitee_counts,
    }
    if include_invitees:
        data["invitees"] = [_invitee_to_dict(i) for i in invitation.invitees]
    return data


def _apply_invitation_fields(invitation: Invitation, data: dict, partial: bool = False) -> Optional[str]:
    field_map = {
        "title": "title",
        "course_title": "course_title",
        "course_description": "course_description",
        "venue": "venue",
        "learning_outcomes": "learning_outcomes",
        "source_email": "source_email",
        "email_subject": "email_subject",
        "email_message": "email_message",
        "bank_account_name": "bank_account_name",
        "bank_account_number": "bank_account_number",
        "bank_name": "bank_name",
        "invitation_template_path": "invitation_template_path",
        "invitation_template_filename": "invitation_template_filename",
    }
    for json_key, attr in field_map.items():
        if json_key in data:
            setattr(invitation, attr, data[json_key])

    if "start_date" in data:
        invitation.start_date = _parse_date(data["start_date"], "start_date")
    if "end_date" in data:
        invitation.end_date = _parse_date(data["end_date"], "end_date")
    if "reservation_deadline" in data:
        invitation.reservation_deadline = (
            _parse_date(data["reservation_deadline"], "reservation_deadline")
            if data["reservation_deadline"] else None
        )
    if "start_time" in data:
        invitation.start_time = _parse_time(data["start_time"], "start_time")
    if "end_time" in data:
        invitation.end_time = _parse_time(data["end_time"], "end_time")
    if "scheduled_at" in data:
        invitation.scheduled_at = _parse_datetime_optional(data["scheduled_at"])
    if "course_fee" in data:
        invitation.course_fee = _decimal_optional(data["course_fee"])
    if "deposit_amount" in data:
        invitation.deposit_amount = _decimal_optional(data["deposit_amount"])
    if "interval_seconds" in data:
        invitation.interval_seconds = int(data["interval_seconds"])
    if "interval_limit" in data:
        invitation.interval_limit = int(data["interval_limit"])

    if not partial:
        string_fields = (
            "title", "course_title", "course_description", "venue",
            "source_email", "email_subject", "email_message",
        )
        for key in string_fields:
            if not (getattr(invitation, key) or "").strip():
                return f"Missing required field: {key}"
        for key in ("start_date", "end_date", "start_time", "end_time"):
            if getattr(invitation, key) is None:
                return f"Missing required field: {key}"

        if not EMAIL_RE.match(invitation.source_email or ""):
            return "Invalid source_email"
        if invitation.interval_seconds is not None and invitation.interval_seconds < 0:
            return "interval_seconds must be >= 0"
        if invitation.interval_limit is not None and invitation.interval_limit < 1:
            return "interval_limit must be >= 1"

    return None


def _get_invitation_or_404(db, invitation_id: int):
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        return None, (jsonify({"status": "error", "message": "Invitation not found"}), 404)
    return invitation, None


def _require_editable_status(invitation: Invitation):
    if invitation.status not in (
        InvitationCampaignStatus.draft,
        InvitationCampaignStatus.validated,
        InvitationCampaignStatus.scheduled,
    ):
        return jsonify({
            "status": "error",
            "message": f"Invitation cannot be edited in status {invitation.status.value}",
        }), 400
    return None


# ---------------------------------------------------------------------------
# Trainers
# ---------------------------------------------------------------------------

@invitations_bp.route("/api/invitations/trainers", methods=["GET"])
@jwt_required()
def list_invitation_trainers():
    db = get_db()
    try:
        active_only = request.args.get("active_only", "true").lower() != "false"
        q = db.query(InvitationTrainer)
        if active_only:
            q = q.filter(InvitationTrainer.is_active == True)
        trainers = q.order_by(InvitationTrainer.full_name.asc()).all()
        return jsonify({
            "status": "success",
            "data": [_trainer_to_dict(t) for t in trainers],
        })
    except Exception as e:
        logger.exception("list_invitation_trainers: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/trainers/<int:trainer_id>", methods=["GET"])
@jwt_required()
def get_invitation_trainer(trainer_id: int):
    db = get_db()
    try:
        trainer = db.query(InvitationTrainer).filter(InvitationTrainer.id == trainer_id).first()
        if not trainer:
            return jsonify({"status": "error", "message": "Trainer not found"}), 404
        return jsonify({"status": "success", "data": _trainer_to_dict(trainer)})
    except Exception as e:
        logger.exception("get_invitation_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/trainers", methods=["POST"])
@jwt_required()
def create_invitation_trainer():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        photo_url = None
        if request.content_type and "multipart/form-data" in request.content_type:
            data = {
                "full_name": request.form.get("full_name"),
                "designation": request.form.get("designation"),
                "bio": request.form.get("bio"),
                "qualifications": request.form.get("qualifications"),
            }
            if "photo" in request.files:
                photo_url = handle_invitation_trainer_photo_upload(
                    request.files["photo"], data.get("full_name") or ""
                )
        else:
            data = request.get_json(silent=True) or {}
            photo_url = data.get("photo")

        if not (data.get("full_name") or "").strip():
            return jsonify({"status": "error", "message": "full_name is required"}), 400

        trainer = InvitationTrainer(
            full_name=data["full_name"].strip(),
            designation=(data.get("designation") or "").strip() or None,
            bio=(data.get("bio") or "").strip() or None,
            qualifications=(data.get("qualifications") or "").strip() or None,
            photo=photo_url,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(trainer)
        db.commit()
        db.refresh(trainer)
        return jsonify({
            "status": "success",
            "message": "Trainer created",
            "data": _trainer_to_dict(trainer),
        }), 201
    except Exception as e:
        db.rollback()
        logger.exception("create_invitation_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/trainers/<int:trainer_id>", methods=["PUT"])
@jwt_required()
def update_invitation_trainer(trainer_id: int):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        trainer = db.query(InvitationTrainer).filter(InvitationTrainer.id == trainer_id).first()
        if not trainer:
            return jsonify({"status": "error", "message": "Trainer not found"}), 404

        if request.content_type and "multipart/form-data" in request.content_type:
            data = request.form.to_dict()
            if "photo" in request.files and request.files["photo"].filename:
                photo_url = handle_invitation_trainer_photo_upload(
                    request.files["photo"], data.get("full_name") or trainer.full_name
                )
                if photo_url:
                    trainer.photo = photo_url
        else:
            data = request.get_json(silent=True) or {}

        for field in ("full_name", "designation", "bio", "qualifications", "photo"):
            if field in data and data[field] is not None:
                value = data[field]
                if field != "photo":
                    value = str(value).strip() or None
                setattr(trainer, field, value if field != "full_name" else (value or trainer.full_name))
        if "is_active" in data:
            trainer.is_active = bool(data["is_active"])

        trainer.updated_by = user_id
        trainer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(trainer)
        return jsonify({
            "status": "success",
            "message": "Trainer updated",
            "data": _trainer_to_dict(trainer),
        })
    except Exception as e:
        db.rollback()
        logger.exception("update_invitation_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/trainers/<int:trainer_id>", methods=["DELETE"])
@jwt_required()
def delete_invitation_trainer(trainer_id: int):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        trainer = db.query(InvitationTrainer).filter(InvitationTrainer.id == trainer_id).first()
        if not trainer:
            return jsonify({"status": "error", "message": "Trainer not found"}), 404
        trainer.is_active = False
        trainer.updated_by = user_id
        trainer.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"status": "success", "message": "Trainer deactivated"})
    except Exception as e:
        db.rollback()
        logger.exception("delete_invitation_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------

@invitations_bp.route("/api/invitations", methods=["POST"])
@jwt_required()
def create_invitation():
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation = Invitation(
            status=InvitationCampaignStatus.draft,
            interval_seconds=int(data.get("interval_seconds", 10)),
            interval_limit=int(data.get("interval_limit", 5)),
            created_by=user_id,
            updated_by=user_id,
        )
        error = _apply_invitation_fields(invitation, data, partial=False)
        if error:
            return jsonify({"status": "error", "message": error}), 400

        db.add(invitation)
        db.flush()

        trainer_ids = data.get("trainer_ids") or []
        if trainer_ids:
            _assign_trainers(db, invitation, trainer_ids)

        db.commit()
        db.refresh(invitation)
        return jsonify({
            "status": "success",
            "message": "Invitation created",
            "data": _invitation_to_dict(invitation),
        }), 201
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("create_invitation: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations", methods=["GET"])
@jwt_required()
def list_invitations():
    db = get_db()
    try:
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
        status_filter = (request.args.get("status") or "").strip().upper() or None
        offset = (page - 1) * per_page

        q = db.query(Invitation)
        if status_filter:
            try:
                status_enum = InvitationCampaignStatus[status_filter.lower()]
            except KeyError:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid status: {status_filter}",
                }), 400
            q = q.filter(Invitation.status == status_enum)
        total = q.count()
        rows = (
            q.order_by(Invitation.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        return jsonify({
            "status": "success",
            "data": {
                "invitations": [
                    _invitation_to_dict(r, include_trainers=False) for r in rows
                ],
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page if total else 0,
                },
            },
        })
    except Exception as e:
        logger.exception("list_invitations: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/<int:invitation_id>", methods=["GET"])
@jwt_required()
def get_invitation(invitation_id: int):
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        include_invitees = request.args.get("include_invitees", "false").lower() == "true"
        return jsonify({
            "status": "success",
            "data": _invitation_to_dict(invitation, include_invitees=include_invitees),
        })
    except Exception as e:
        logger.exception("get_invitation: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/<int:invitation_id>", methods=["PUT"])
@jwt_required()
def update_invitation(invitation_id: int):
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_editable_status(invitation)
        if blocked:
            return blocked

        error = _apply_invitation_fields(invitation, data, partial=True)
        if error:
            return jsonify({"status": "error", "message": error}), 400

        invitation.updated_by = user_id
        invitation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(invitation)
        return jsonify({
            "status": "success",
            "message": "Invitation updated",
            "data": _invitation_to_dict(invitation),
        })
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("update_invitation: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/<int:invitation_id>", methods=["DELETE"])
@jwt_required()
def cancel_invitation(invitation_id: int):
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        if invitation.status == InvitationCampaignStatus.processing:
            return jsonify({
                "status": "error",
                "message": "Cannot cancel an invitation that is PROCESSING",
            }), 400
        invitation.status = InvitationCampaignStatus.cancelled
        invitation.updated_by = user_id
        invitation.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"status": "success", "message": "Invitation cancelled"})
    except Exception as e:
        db.rollback()
        logger.exception("cancel_invitation: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


def _assign_trainers(db, invitation: Invitation, trainer_ids: List[int]) -> None:
    trainers = (
        db.query(InvitationTrainer)
        .filter(InvitationTrainer.id.in_(trainer_ids))
        .filter(InvitationTrainer.is_active == True)
        .all()
    )
    found_ids = {t.id for t in trainers}
    missing = [tid for tid in trainer_ids if tid not in found_ids]
    if missing:
        raise ValueError(f"Trainer(s) not found or inactive: {missing}")

    invitation.trainer_assignments.clear()
    db.flush()
    for order, trainer_id in enumerate(trainer_ids):
        db.add(
            InvitationTrainerAssignment(
                invitation_id=invitation.id,
                trainer_id=trainer_id,
                display_order=order,
            )
        )


@invitations_bp.route("/api/invitations/<int:invitation_id>/trainers", methods=["POST"])
@jwt_required()
def assign_invitation_trainers(invitation_id: int):
    """
    Assign trainers to an invitation (replaces existing assignments).

    Body: { "trainer_ids": [1, 2, 3] }
    """
    data = request.get_json(silent=True) or {}
    trainer_ids = data.get("trainer_ids")
    if not isinstance(trainer_ids, list):
        return jsonify({"status": "error", "message": "trainer_ids must be an array"}), 400

    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_editable_status(invitation)
        if blocked:
            return blocked

        _assign_trainers(db, invitation, [int(t) for t in trainer_ids])
        invitation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(invitation)
        return jsonify({
            "status": "success",
            "message": "Trainers assigned",
            "data": _invitation_to_dict(invitation),
        })
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("assign_invitation_trainers: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Invitees (Phase 2 — JSON array from frontend)
# ---------------------------------------------------------------------------

def _invitee_validation_status_filter(value: str):
    try:
        return InviteeValidationStatus[value.strip().lower()]
    except KeyError:
        raise ValueError(
            f"Invalid validation_status: {value}. "
            "Use PENDING, VALID, INVALID, or DUPLICATE"
        )


def _invitee_send_status_filter(value: str):
    try:
        return InviteeSendStatus[value.strip().lower()]
    except KeyError:
        raise ValueError(
            f"Invalid send_status: {value}. "
            "Use PENDING, SENDING, SENT, or FAILED"
        )


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/invitees/validate",
    methods=["POST"],
)
@jwt_required()
def validate_invitation_invitees(invitation_id: int):
    """
    Dry-run validation — does not persist invitees.

    Body: {
      "invitees": [
        { "full_name": "...", "email": "...", "address": "...", "organization": "..." }
      ]
    }
    """
    data = request.get_json(silent=True) or {}
    invitees = data.get("invitees")
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err

        validated_rows, summary = validate_invitee_rows(invitees)
        return jsonify({
            "status": "success",
            "data": {
                "invitation_id": invitation.id,
                "summary": summary,
                "invitees": validated_rows,
            },
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception("validate_invitation_invitees: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/<int:invitation_id>/invitees", methods=["POST"])
@jwt_required()
def upload_invitation_invitees(invitation_id: int):
    """
    Validate and save invitees (replaces existing by default).

    Body: {
      "replace": true,
      "invitees": [
        { "full_name": "...", "email": "...", "address": "...", "organization": "..." }
      ]
    }
    """
    data = request.get_json(silent=True) or {}
    invitees = data.get("invitees")
    replace = data.get("replace", True)
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_editable_status(invitation)
        if blocked:
            return blocked

        saved, summary = sync_invitation_invitees(
            db,
            invitation,
            invitees,
            replace=bool(replace),
            user_id=user_id,
        )
        db.commit()
        return jsonify({
            "status": "success",
            "message": "Invitees saved",
            "data": {
                "invitation_id": invitation.id,
                "invitation_status": invitation.status.value,
                "summary": summary,
                "invitees": [_invitee_to_dict(i) for i in saved],
            },
        })
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("upload_invitation_invitees: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route("/api/invitations/<int:invitation_id>/invitees", methods=["GET"])
@jwt_required()
def list_invitation_invitees(invitation_id: int):
    """
    List invitees with optional filters and pagination.

    Query: ?page=1&per_page=50&validation_status=VALID&send_status=PENDING
    """
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err

        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(200, max(1, request.args.get("per_page", 50, type=int)))
        offset = (page - 1) * per_page

        q = db.query(InvitationInvitee).filter(
            InvitationInvitee.invitation_id == invitation_id
        )

        validation_status = (request.args.get("validation_status") or "").strip()
        if validation_status:
            q = q.filter(
                InvitationInvitee.validation_status
                == _invitee_validation_status_filter(validation_status)
            )

        send_status = (request.args.get("send_status") or "").strip()
        if send_status:
            q = q.filter(
                InvitationInvitee.send_status == _invitee_send_status_filter(send_status)
            )

        total = q.count()
        rows = (
            q.order_by(InvitationInvitee.id.asc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        all_invitees = invitation.invitees
        return jsonify({
            "status": "success",
            "data": {
                "invitation_id": invitation.id,
                "summary": build_invitee_summary(all_invitees),
                "invitees": [_invitee_to_dict(i) for i in rows],
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page if total else 0,
                },
            },
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception("list_invitation_invitees: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/invitees/summary",
    methods=["GET"],
)
@jwt_required()
def invitation_invitees_summary(invitation_id: int):
    """Validation and send counts for the invitation invitee list."""
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        return jsonify({
            "status": "success",
            "data": {
                "invitation_id": invitation.id,
                "invitation_status": invitation.status.value,
                "summary": build_invitee_summary(invitation.invitees),
            },
        })
    except Exception as e:
        logger.exception("invitation_invitees_summary: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/invitees",
    methods=["DELETE"],
)
@jwt_required()
def clear_invitation_invitees(invitation_id: int):
    """Remove all invitees from an invitation."""
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_editable_status(invitation)
        if blocked:
            return blocked

        deleted = (
            db.query(InvitationInvitee)
            .filter(InvitationInvitee.invitation_id == invitation_id)
            .delete(synchronize_session=False)
        )
        if invitation.status == InvitationCampaignStatus.validated:
            invitation.status = InvitationCampaignStatus.draft
        invitation.updated_by = user_id
        invitation.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({
            "status": "success",
            "message": f"Removed {deleted} invitee(s)",
            "data": {"deleted": deleted},
        })
    except Exception as e:
        db.rollback()
        logger.exception("clear_invitation_invitees: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Preview & templates (Phase 3 — Jinja2 HTML + PDF)
# ---------------------------------------------------------------------------

def _resolve_preview_invitee(
    db,
    invitation: Invitation,
    *,
    invitee_id: Optional[int] = None,
    use_sample: bool = False,
    override: Optional[dict] = None,
) -> tuple:
    """
    Resolve invitee data for preview.

    Returns (invitee_dict, meta_dict) or raises ValueError.
    """
    if override:
        invitee = {
            "full_name": (override.get("full_name") or "").strip(),
            "email": (override.get("email") or "").strip(),
            "address": override.get("address"),
            "organization": override.get("organization"),
        }
        if not invitee["full_name"]:
            raise ValueError("invitee.full_name is required for preview")
        return invitee, {"is_sample": False, "invitee_id": override.get("id")}

    if use_sample:
        return sample_invitee_dict(), {"is_sample": True, "invitee_id": None}

    if invitee_id:
        invitee_model = (
            db.query(InvitationInvitee)
            .filter(
                InvitationInvitee.id == invitee_id,
                InvitationInvitee.invitation_id == invitation.id,
            )
            .first()
        )
        if not invitee_model:
            raise ValueError("Invitee not found for this invitation")
        return invitee_dict_from_model(invitee_model), {
            "is_sample": False,
            "invitee_id": invitee_model.id,
        }

    invitee_model = (
        db.query(InvitationInvitee)
        .filter(
            InvitationInvitee.invitation_id == invitation.id,
            InvitationInvitee.validation_status == InviteeValidationStatus.valid,
        )
        .order_by(InvitationInvitee.id.asc())
        .first()
    )
    if invitee_model:
        return invitee_dict_from_model(invitee_model), {
            "is_sample": False,
            "invitee_id": invitee_model.id,
        }

    return sample_invitee_dict(), {"is_sample": True, "invitee_id": None}


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/preview/html",
    methods=["GET", "POST"],
)
@jwt_required()
def preview_invitation_html(invitation_id: int):
    """
    Render invitation HTML (7 sections).

    GET query params:
      - invitee_id: use a saved invitee
      - sample=true: force sample invitee data
      - format=json|html (default json)

    POST body (optional):
      { "invitee": { "full_name", "email", "address", "organization" } }
    """
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err

        override = None
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            override = body.get("invitee")

        invitee_id = request.args.get("invitee_id", type=int)
        use_sample = request.args.get("sample", "false").lower() == "true"
        output_format = (request.args.get("format") or "json").lower()

        invitee, meta = _resolve_preview_invitee(
            db,
            invitation,
            invitee_id=invitee_id,
            use_sample=use_sample,
            override=override,
        )

        html_content = render_invitation_html(
            invitation,
            invitee,
            template_path=invitation.invitation_template_path,
        )

        if output_format == "html":
            return Response(html_content, mimetype="text/html")

        return jsonify({
            "status": "success",
            "data": {
                "invitation_id": invitation.id,
                "preview": meta,
                "invitee": invitee,
                "has_custom_template": bool(invitation.invitation_template_path),
                "html": html_content,
                "context": build_invitation_render_context(invitation, invitee),
            },
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception("preview_invitation_html: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/preview/pdf",
    methods=["GET", "POST"],
)
@jwt_required()
def preview_invitation_pdf(invitation_id: int):
    """
    Download a sample or personalized invitation PDF.

    GET query: invitee_id, sample=true
    POST body: optional { "invitee": { ... } }
    """
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err

        override = None
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            override = body.get("invitee")

        invitee_id = request.args.get("invitee_id", type=int)
        use_sample = request.args.get("sample", "false").lower() == "true"

        if override or invitee_id or use_sample:
            invitee, _meta = _resolve_preview_invitee(
                db,
                invitation,
                invitee_id=invitee_id,
                use_sample=use_sample,
                override=override,
            )
            pdf_bytes, filename = render_invitation_pdf_bytes(invitation, invitee)
        else:
            pdf_bytes, filename = render_sample_invitation_pdf(invitation)

        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logger.exception("preview_invitation_pdf: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/template",
    methods=["POST"],
)
@jwt_required()
def upload_invitation_campaign_template(invitation_id: int):
    """
    Upload a custom Jinja2 HTML template for this invitation.

    multipart/form-data field: template (HTML file).
    Must include {{ invitee.full_name }} or invitee.full_name in Jinja2 syntax.
    """
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_editable_status(invitation)
        if blocked:
            return blocked

        file_storage = request.files.get("template")
        template_error = validate_campaign_template_upload(file_storage)
        if template_error:
            return jsonify({"status": "error", "message": template_error}), 400

        delete_campaign_template_file(invitation.invitation_template_path)
        path, filename = save_campaign_template(invitation_id, file_storage)
        invitation.invitation_template_path = path
        invitation.invitation_template_filename = filename
        invitation.updated_by = user_id
        invitation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(invitation)

        return jsonify({
            "status": "success",
            "message": "Invitation template uploaded",
            "data": {
                "invitation_id": invitation.id,
                "has_template": True,
                "invitation_template_filename": filename,
            },
        })
    except Exception as e:
        db.rollback()
        logger.exception("upload_invitation_campaign_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/template",
    methods=["DELETE"],
)
@jwt_required()
def remove_invitation_campaign_template(invitation_id: int):
    """Remove custom template; built-in Jinja2 default will be used."""
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_editable_status(invitation)
        if blocked:
            return blocked

        if not invitation.invitation_template_path:
            return jsonify({"status": "error", "message": "No custom template on this invitation"}), 404

        delete_campaign_template_file(invitation.invitation_template_path)
        invitation.invitation_template_path = None
        invitation.invitation_template_filename = None
        invitation.updated_by = user_id
        invitation.updated_at = datetime.utcnow()
        db.commit()

        return jsonify({
            "status": "success",
            "message": "Custom template removed; default template will be used",
            "data": {"invitation_id": invitation.id, "has_template": False},
        })
    except Exception as e:
        db.rollback()
        logger.exception("remove_invitation_campaign_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/template",
    methods=["GET"],
)
@jwt_required()
def download_invitation_campaign_template(invitation_id: int):
    """Download the custom Jinja2 HTML template."""
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        if not invitation.invitation_template_path or not Path(
            invitation.invitation_template_path
        ).is_file():
            return jsonify({
                "status": "error",
                "message": "No custom template; built-in default is used",
            }), 404
        return send_file(
            invitation.invitation_template_path,
            mimetype="text/html",
            as_attachment=True,
            download_name=invitation.invitation_template_filename or "invitation_template.html",
        )
    except Exception as e:
        logger.exception("download_invitation_campaign_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/template/default",
    methods=["GET"],
)
@jwt_required()
def download_default_invitation_template(invitation_id: int):
    """Download the built-in Jinja2 template for customization reference."""
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        default_path = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / "invitations"
            / "invitation_letter.html"
        )
        if not default_path.is_file():
            return jsonify({"status": "error", "message": "Default template not found"}), 404
        return send_file(
            str(default_path),
            mimetype="text/html",
            as_attachment=True,
            download_name="invitation_letter_default.html",
        )
    except Exception as e:
        logger.exception("download_default_invitation_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Sending (Phase 4 — test, schedule, batch send)
# ---------------------------------------------------------------------------

def _require_batch_sendable_status(invitation: Invitation):
    if invitation.status in (
        InvitationCampaignStatus.cancelled,
        InvitationCampaignStatus.completed,
    ):
        return jsonify({
            "status": "error",
            "message": f"Cannot send invitation in status {invitation.status.value}",
        }), 400
    if invitation.status == InvitationCampaignStatus.draft:
        return jsonify({
            "status": "error",
            "message": "Upload and validate invitees before sending",
        }), 400
    return None


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/send/test",
    methods=["POST"],
)
@jwt_required()
def send_invitation_test_email(invitation_id: int):
    """
    Send a one-off test email with personalized PDF (does not update invitee status).

    Body: {
      "email": "you@example.com",
      "invitee_id": 5,
      "invitee": { "full_name", "email", "address", "organization" }
    }
    """
    data = request.get_json(silent=True) or {}
    test_email = (data.get("email") or "").strip()
    if not test_email:
        return jsonify({"status": "error", "message": "email is required"}), 400
    if not EMAIL_RE.match(test_email):
        return jsonify({"status": "error", "message": "Invalid email address"}), 400

    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        if invitation.status == InvitationCampaignStatus.cancelled:
            return jsonify({
                "status": "error",
                "message": "Cannot send test email for a cancelled invitation",
            }), 400

        invitee, _meta = _resolve_preview_invitee(
            db,
            invitation,
            invitee_id=data.get("invitee_id"),
            use_sample=not data.get("invitee_id") and not data.get("invitee"),
            override=data.get("invitee"),
        )

        ok, error_message, pdf_filename = send_test_invitation_email(
            invitation,
            invitee,
            test_email,
        )
        if not ok:
            return jsonify({
                "status": "error",
                "message": error_message or "Failed to send test email",
            }), 500

        return jsonify({
            "status": "success",
            "message": f"Test email sent to {test_email}",
            "data": {
                "invitation_id": invitation.id,
                "sent_to": test_email,
                "pdf_filename": pdf_filename,
                "invitee": invitee,
            },
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception("send_invitation_test_email: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/send/schedule",
    methods=["POST"],
)
@jwt_required()
def schedule_invitation_send(invitation_id: int):
    """
    Schedule campaign sending for a future time.

    Body: { "scheduled_at": "2025-06-15T10:00:00" }
    """
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_batch_sendable_status(invitation)
        if blocked:
            return blocked
        if invitation.status == InvitationCampaignStatus.processing:
            return jsonify({
                "status": "error",
                "message": "Cannot schedule while invitation is PROCESSING",
            }), 400

        if not data.get("scheduled_at"):
            return jsonify({"status": "error", "message": "scheduled_at is required"}), 400

        scheduled_at = _parse_datetime_optional(data["scheduled_at"])
        if scheduled_at <= datetime.utcnow():
            return jsonify({
                "status": "error",
                "message": "scheduled_at must be in the future",
            }), 400

        pending = count_pending_valid_invitees(db, invitation_id)
        if pending == 0:
            return jsonify({
                "status": "error",
                "message": "No valid pending invitees to send",
            }), 400

        invitation.scheduled_at = scheduled_at
        invitation.status = InvitationCampaignStatus.scheduled
        invitation.updated_by = user_id
        invitation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(invitation)

        return jsonify({
            "status": "success",
            "message": "Invitation send scheduled",
            "data": {
                "invitation_id": invitation.id,
                "status": invitation.status.value,
                "scheduled_at": invitation.scheduled_at.isoformat(),
                "pending_recipients": pending,
            },
        })
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("schedule_invitation_send: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitations_bp.route(
    "/api/invitations/<int:invitation_id>/send/start",
    methods=["POST"],
)
@jwt_required()
def start_invitation_send(invitation_id: int):
    """
    Start or resume sending to all valid pending invitees.

    Body (optional): { "force": false, "retry_failed": false }
    """
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))
    retry_failed = bool(data.get("retry_failed", False))
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        invitation, err = _get_invitation_or_404(db, invitation_id)
        if err:
            return err
        blocked = _require_batch_sendable_status(invitation)
        if blocked:
            return blocked

        if invitation.status == InvitationCampaignStatus.completed:
            return jsonify({
                "status": "error",
                "message": "Invitation is already COMPLETED",
            }), 400

        if (
            invitation.status == InvitationCampaignStatus.scheduled
            and invitation.scheduled_at
            and invitation.scheduled_at > datetime.utcnow()
            and not force
        ):
            return jsonify({
                "status": "error",
                "message": (
                    "Invitation is scheduled for the future. "
                    "Use force=true to send immediately."
                ),
                "data": {"scheduled_at": invitation.scheduled_at.isoformat()},
            }), 400

        pending = count_pending_valid_invitees(
            db,
            invitation_id,
            include_failed=retry_failed,
        )
        if pending == 0:
            return jsonify({
                "status": "error",
                "message": "No valid pending invitees to send",
            }), 400

        resuming = invitation.status == InvitationCampaignStatus.processing
        if not resuming:
            invitation.status = InvitationCampaignStatus.processing
            invitation.started_at = datetime.utcnow()
            invitation.updated_by = user_id
            invitation.updated_at = datetime.utcnow()
            db.commit()

        queued_async, already_running = queue_invitation_campaign_processing(
            invitation_id,
            include_failed=retry_failed,
        )
        db.refresh(invitation)

        message = (
            "Invitation sending resumed"
            if resuming
            else "Invitation sending started"
        )
        if already_running:
            message = "Invitation is already processing in this server worker"

        return jsonify({
            "status": "success",
            "message": message,
            "data": {
                "invitation_id": invitation.id,
                "status": invitation.status.value,
                "pending_recipients": pending,
                "queued_via_celery": queued_async,
                "resumed": resuming,
                "already_running": already_running,
                "retry_failed": retry_failed,
            },
        })
    except Exception as e:
        db.rollback()
        logger.exception("start_invitation_send: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()
