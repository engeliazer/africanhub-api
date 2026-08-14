"""
Simple events / public invitations API.

Admin: create and list upcoming events.
Public: list published events and download personalized invitation letters (PDF).
"""

import logging
from datetime import date, datetime, time as time_type
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import joinedload
from sqlalchemy import true
from sqlalchemy.exc import IntegrityError

from certificates.models.models import Salutation
from applications.models.models import InvitationTrainer
from database.db_connector import get_db
from events.models.models import Event, EventLetterRequest, EventTrainerAssignment
from events.services.event_letter_request_service import (
    build_invitee_from_letter_request,
    build_letter_invitee_full_name,
    find_existing_letter_request,
    find_letter_request_by_id,
    generate_verification_code,
    get_salutation_or_error,
    is_verification_required,
    letter_request_to_dict,
    send_phone_verification_sms,
    validate_letter_request_payload,
    validate_phone_verification_payload,
    verification_codes_match,
)
from public.controllers.invitation_trainer_photo_utils import handle_invitation_trainer_photo_upload
from public.services.invitation_campaign_pdf_service import render_event_invitation_pdf_bytes
from public.services.invitation_template_service import (
    delete_invitation_template_file,
    save_invitation_template,
    validate_html_template_upload,
)

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__)


def _parse_date(value: str, field: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    raise ValueError(f"{field} must be YYYY-MM-DD or DD/MM/YYYY")


def _parse_time_optional(value) -> Optional[time_type]:
    if value in (None, ""):
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(str(value).strip(), fmt).time()
        except ValueError:
            continue
    raise ValueError("start_time/end_time must be HH:MM or HH:MM:SS")


def _parse_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _decimal_optional(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _format_date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _format_time(value: Optional[time_type]) -> Optional[str]:
    return value.strftime("%H:%M:%S") if value else None


def _payment_dict(event: Event) -> Dict[str, Any]:
    return {
        "course_fee": float(event.course_fee) if event.course_fee is not None else None,
        "deposit_amount": float(event.deposit_amount) if event.deposit_amount is not None else None,
        "reservation_deadline": _format_date(event.reservation_deadline),
        "bank_account_name": event.bank_account_name,
        "bank_account_number": event.bank_account_number,
        "bank_name": event.bank_name,
    }


def _trainer_to_dict(trainer: InvitationTrainer, *, public: bool = False, display_order: int = 0) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": trainer.id,
        "full_name": trainer.full_name,
        "designation": trainer.designation,
        "bio": trainer.bio,
        "qualifications": trainer.qualifications,
        "photo": trainer.photo,
        "display_order": display_order,
    }
    if not public:
        data.update({
            "is_active": trainer.is_active,
            "created_by": trainer.created_by,
            "updated_by": trainer.updated_by,
            "created_at": trainer.created_at.isoformat() if trainer.created_at else None,
            "updated_at": trainer.updated_at.isoformat() if trainer.updated_at else None,
        })
    return data


def _trainers_for_event(event: Event, db, *, public: bool = False) -> List[Dict[str, Any]]:
    assignments = sorted(event.trainer_assignments, key=lambda a: (a.display_order, a.id))
    if not assignments:
        return []

    trainer_ids = [a.trainer_id for a in assignments]
    trainers = (
        db.query(InvitationTrainer)
        .filter(InvitationTrainer.id.in_(trainer_ids))
        .all()
    )
    trainer_map = {t.id: t for t in trainers}

    result = []
    for assignment in assignments:
        trainer = trainer_map.get(assignment.trainer_id)
        if trainer and (not public or trainer.is_active):
            result.append(_trainer_to_dict(trainer, public=public, display_order=assignment.display_order))
    return result


def _send_event_letter_pdf(event: Event, invitee: Dict[str, Any], db):
    trainers = _trainers_for_event(event, db, public=True)
    pdf_bytes, filename = render_event_invitation_pdf_bytes(event, invitee, trainers)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


def _event_to_dict(
    event: Event,
    db,
    *,
    public: bool = False,
    setup_detail: str = "full",
) -> Dict[str, Any]:
    """
    setup_detail: 'full' | 'summary' | 'none' (admin only; ignored for public)
    """
    data: Dict[str, Any] = {
        "id": event.id,
        "title": event.title,
        "course_title": event.course_title,
        "course_description": event.course_description,
        "venue": event.venue,
        "start_date": _format_date(event.start_date),
        "end_date": _format_date(event.end_date),
        "start_time": _format_time(event.start_time),
        "end_time": _format_time(event.end_time),
        "learning_outcomes": event.learning_outcomes,
        "payment": _payment_dict(event),
        "trainers": _trainers_for_event(event, db, public=public),
    }
    if not public:
        data.update({
            "is_published": event.is_published,
            "has_template": bool(event.invitation_template_path),
            "invitation_template_filename": event.invitation_template_filename,
            "uses_default_template": not bool(event.invitation_template_path),
            "created_by": event.created_by,
            "updated_by": event.updated_by,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "updated_at": event.updated_at.isoformat() if event.updated_at else None,
        })
        if setup_detail == "full":
            data["setup"] = build_event_setup(event, db, detailed=True)
        elif setup_detail == "summary":
            data["setup"] = build_event_setup(event, db, detailed=False)
    return data


def _events_query(db):
    return db.query(Event).options(joinedload(Event.trainer_assignments))


def _upcoming_filter(query, today: date):
    return query.filter(Event.end_date >= today)


def _get_event_or_404(db, event_id: int):
    event = (
        _events_query(db)
        .filter(Event.id == event_id)
        .first()
    )
    if not event:
        return None, (jsonify({"status": "error", "message": "Event not found"}), 404)
    return event, None


def _apply_payment_fields(event: Event, data: dict) -> None:
    if "course_fee" in data:
        event.course_fee = _decimal_optional(data.get("course_fee"))
    if "deposit_amount" in data:
        event.deposit_amount = _decimal_optional(data.get("deposit_amount"))
    if "reservation_deadline" in data:
        value = data.get("reservation_deadline")
        event.reservation_deadline = _parse_date(value, "reservation_deadline") if value else None
    if "bank_account_name" in data:
        event.bank_account_name = (data.get("bank_account_name") or "").strip() or None
    if "bank_account_number" in data:
        event.bank_account_number = (data.get("bank_account_number") or "").strip() or None
    if "bank_name" in data:
        event.bank_name = (data.get("bank_name") or "").strip() or None


def _assign_trainers(db, event: Event, trainer_ids: List[int]) -> None:
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

    event.trainer_assignments.clear()
    db.flush()
    for order, trainer_id in enumerate(trainer_ids):
        db.add(
            EventTrainerAssignment(
                event_id=event.id,
                trainer_id=trainer_id,
                display_order=order,
            )
        )


def _flatten_event_input(data: dict) -> dict:
    """Merge nested payment object into top-level fields for create/update helpers."""
    flat = dict(data)
    payment = flat.pop("payment", None)
    if isinstance(payment, dict):
        for key in (
            "course_fee", "deposit_amount", "reservation_deadline",
            "bank_account_name", "bank_account_number", "bank_name",
        ):
            if key in payment and key not in flat:
                flat[key] = payment[key]
    flat.pop("trainers", None)
    return flat


def _apply_create_fields(event: Event, data: dict) -> Optional[str]:
    title = (data.get("title") or "").strip()
    course_title = (data.get("course_title") or "").strip()
    venue = (data.get("venue") or "").strip()
    if not title:
        return "title is required"
    if not course_title:
        return "course_title is required"
    if not venue:
        return "venue is required"
    if not data.get("start_date"):
        return "start_date is required"
    if not data.get("end_date"):
        return "end_date is required"

    try:
        start_date = _parse_date(data["start_date"], "start_date")
        end_date = _parse_date(data["end_date"], "end_date")
        start_time = _parse_time_optional(data.get("start_time"))
        end_time = _parse_time_optional(data.get("end_time"))
    except ValueError as exc:
        return str(exc)

    if end_date < start_date:
        return "end_date must be on or after start_date"

    event.title = title
    event.course_title = course_title
    event.course_description = (data.get("course_description") or "").strip() or None
    event.venue = venue
    event.start_date = start_date
    event.end_date = end_date
    event.start_time = start_time
    event.end_time = end_time
    event.learning_outcomes = (data.get("learning_outcomes") or "").strip() or None
    _apply_payment_fields(event, data)
    return None


def _parse_create_payload():
    if request.content_type and "multipart/form-data" in request.content_type:
        trainer_ids_raw = request.form.get("trainer_ids")
        trainer_ids = None
        if trainer_ids_raw:
            import json
            trainer_ids = json.loads(trainer_ids_raw) if trainer_ids_raw.startswith("[") else [
                int(x.strip()) for x in trainer_ids_raw.split(",") if x.strip()
            ]
        return {
            "title": request.form.get("title"),
            "course_title": request.form.get("course_title"),
            "course_description": request.form.get("course_description"),
            "venue": request.form.get("venue"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "start_time": request.form.get("start_time"),
            "end_time": request.form.get("end_time"),
            "learning_outcomes": request.form.get("learning_outcomes"),
            "course_fee": request.form.get("course_fee"),
            "deposit_amount": request.form.get("deposit_amount"),
            "reservation_deadline": request.form.get("reservation_deadline"),
            "bank_account_name": request.form.get("bank_account_name"),
            "bank_account_number": request.form.get("bank_account_number"),
            "bank_name": request.form.get("bank_name"),
            "is_published": request.form.get("is_published"),
            "trainer_ids": trainer_ids,
        }, request.files.get("template")
    return request.get_json(silent=True) or {}, None


def _validate_publish_allowed(event: Event, db) -> Optional[str]:
    setup = build_event_setup(event, db, detailed=False)
    if setup.get("required_steps_complete"):
        return None
    step = setup.get("current_step_label") or "required setup"
    return f"Complete step: {step}."


def _try_publish_event(event: Event, db) -> Optional[str]:
    """Validate and set is_published. Returns error message or None on success."""
    db.flush()
    error = _validate_publish_allowed(event, db)
    if error:
        event.is_published = False
        return error
    event.is_published = True
    return None


@events_bp.route("/api/events", methods=["POST"])
@jwt_required()
def create_event():
    """
    Create a training event / invitation.

    JSON or multipart/form-data. Optional field `template` (HTML file with
    [NAME], [ADDRESS], [ORGANIZATION]) for personalized PDF letters.
    Optional `trainer_ids`: array of invitation_trainer IDs.
    """
    data, template_file = _parse_create_payload()
    data = _flatten_event_input(data)
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        event = Event(created_by=user_id, updated_by=user_id)
        error = _apply_create_fields(event, data)
        if error:
            return jsonify({"status": "error", "message": error}), 400

        db.add(event)
        db.flush()

        trainer_ids = data.get("trainer_ids") or []
        if trainer_ids:
            _assign_trainers(db, event, trainer_ids)

        if template_file and template_file.filename:
            template_error = validate_html_template_upload(template_file)
            if template_error:
                db.rollback()
                return jsonify({"status": "error", "message": template_error}), 400
            path, filename = save_invitation_template(event.id, template_file)
            event.invitation_template_path = path
            event.invitation_template_filename = filename

        wants_publish = _parse_bool(data.get("is_published"), default=False)
        publish_error = None
        if wants_publish:
            publish_error = _try_publish_event(event, db)
        else:
            event.is_published = False

        db.commit()
        db.refresh(event)

        response_message = "Event created"
        if wants_publish and publish_error:
            response_message = f"Event created but not published — {publish_error}"

        return jsonify({
            "status": "success",
            "message": response_message,
            "data": _event_to_dict(event, db),
            "published": bool(event.is_published),
        }), 201
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("create_event: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events", methods=["GET"])
@jwt_required()
def list_events():
    """List events whose end_date has not passed (upcoming or in progress)."""
    db = get_db()
    try:
        today = date.today()
        rows = (
            _upcoming_filter(_events_query(db), today)
            .order_by(Event.start_date.asc(), Event.id.asc())
            .all()
        )
        return jsonify({
            "status": "success",
            "data": [_event_to_dict(row, db, setup_detail="summary") for row in rows],
        })
    except Exception as e:
        logger.exception("list_events: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>", methods=["GET"])
@jwt_required()
def get_event(event_id: int):
    """Get a single event with full setup step progress."""
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err
        return jsonify({
            "status": "success",
            "data": _event_to_dict(event, db, setup_detail="full"),
        })
    except Exception as e:
        logger.exception("get_event: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>/setup", methods=["GET"])
@jwt_required()
def get_event_setup(event_id: int):
    """Setup wizard progress — what is done and what is still missing."""
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err
        return jsonify({
            "status": "success",
            "data": {
                "event_id": event.id,
                "title": event.title,
                **build_event_setup(event, db, detailed=True),
            },
        })
    except Exception as e:
        logger.exception("get_event_setup: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>/publish", methods=["POST"])
@jwt_required()
def publish_event(event_id: int):
    """Publish event to the public website (requires setup steps 1–3 complete)."""
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        user_id = int(get_jwt_identity())
        publish_error = _try_publish_event(event, db)
        event.updated_by = user_id
        event.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(event)

        if publish_error:
            return jsonify({
                "status": "success",
                "message": f"Not published — {publish_error}",
                "published": False,
                "data": _event_to_dict(event, db),
            }), 200

        return jsonify({
            "status": "success",
            "message": "Event published",
            "published": True,
            "data": _event_to_dict(event, db),
        })
    except Exception as e:
        db.rollback()
        logger.exception("publish_event: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>/unpublish", methods=["POST"])
@jwt_required()
def unpublish_event(event_id: int):
    """Remove event from the public website."""
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        event.is_published = False
        event.updated_by = int(get_jwt_identity())
        event.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(event)
        return jsonify({
            "status": "success",
            "message": "Event unpublished",
            "published": False,
            "data": _event_to_dict(event, db),
        })
    except Exception as e:
        db.rollback()
        logger.exception("unpublish_event: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/public", methods=["GET"])
def list_events_public():
    """Public list of published events that have not ended (no authentication)."""
    db = get_db()
    try:
        today = date.today()
        rows = (
            _upcoming_filter(_events_query(db), today)
            .filter(Event.is_published.is_(True))
            .order_by(Event.start_date.asc(), Event.id.asc())
            .all()
        )
        return jsonify({
            "status": "success",
            "data": [_event_to_dict(row, db, public=True) for row in rows],
        })
    except Exception as e:
        logger.exception("list_events_public: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/letter-requests", methods=["GET"])
@jwt_required()
def list_all_letter_requests():
    """List all public invitation letter requests (newest first)."""
    db = get_db()
    try:
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
        event_id = request.args.get("event_id", type=int)
        offset = (page - 1) * per_page

        q = (
            db.query(EventLetterRequest, Event, Salutation)
            .join(Event, EventLetterRequest.event_id == Event.id)
            .join(Salutation, EventLetterRequest.salutation_id == Salutation.id)
        )
        if event_id:
            q = q.filter(EventLetterRequest.event_id == event_id)
        total = q.count()
        rows = (
            q.order_by(EventLetterRequest.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        return jsonify({
            "status": "success",
            "data": {
                "requests": [
                    letter_request_to_dict(req, salutation=salutation, event=event)
                    for req, event, salutation in rows
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
        logger.exception("list_all_letter_requests: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>/letter-requests", methods=["GET"])
@jwt_required()
def list_event_letter_requests(event_id: int):
    """List invitation letter requests for one event."""
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        rows = (
            db.query(EventLetterRequest, Salutation)
            .join(Salutation, EventLetterRequest.salutation_id == Salutation.id)
            .filter(EventLetterRequest.event_id == event_id)
            .order_by(EventLetterRequest.created_at.desc())
            .all()
        )
        return jsonify({
            "status": "success",
            "data": {
                "event_id": event.id,
                "event_title": event.title,
                "total": len(rows),
                "requests": [
                    letter_request_to_dict(req, salutation=salutation)
                    for req, salutation in rows
                ],
            },
        })
    except Exception as e:
        logger.exception("list_event_letter_requests: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/public/<int:event_id>/letter", methods=["POST"])
def request_event_letter(event_id: int):
    """
    Generate and download a personalized invitation letter PDF (no authentication).

    Body: {
      "first_name": "...",
      "middle_name": "...",   // optional
      "last_name": "...",
      "salutation_id": 4,
      "organization": "...",
      "address": "...",
      "email": "...",
      "phone": "..."
    }
    """
    data = request.get_json(silent=True) or {}
    payload, validation_error = validate_letter_request_payload(data)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400

    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        if not event.is_published:
            return jsonify({"status": "error", "message": "Event is not available"}), 404

        if event.end_date < date.today():
            return jsonify({"status": "error", "message": "This event has already ended"}), 410

        salutation, salutation_error = get_salutation_or_error(db, payload["salutation_id"])
        if salutation_error:
            return jsonify({"status": "error", "message": salutation_error}), 400

        existing = find_existing_letter_request(
            db,
            event.id,
            payload["email"],
            payload["phone"],
        )
        letter_request = existing
        if not letter_request:
            try:
                letter_request = EventLetterRequest(
                    event_id=event.id,
                    first_name=payload["first_name"],
                    middle_name=payload["middle_name"],
                    last_name=payload["last_name"],
                    salutation_id=payload["salutation_id"],
                    organization=payload["organization"],
                    address=payload["address"],
                    email=payload["email"],
                    phone=payload["phone"],
                    phone_verification_code=generate_verification_code(),
                    email_verification_code=generate_verification_code(),
                    phone_verified=False,
                    email_verified=False,
                )
                db.add(letter_request)
                db.commit()
                db.refresh(letter_request)
            except IntegrityError:
                db.rollback()
                letter_request = find_existing_letter_request(
                    db,
                    event.id,
                    payload["email"],
                    payload["phone"],
                )

        if not letter_request:
            return jsonify({
                "status": "error",
                "message": "Unable to process letter request",
            }), 500

        if is_verification_required(letter_request):
            letter_request.phone_verification_code = generate_verification_code()
            db.commit()
            sms_ok, sms_message = send_phone_verification_sms(
                letter_request.phone,
                letter_request.phone_verification_code,
                payload["first_name"],
            )
            if not sms_ok:
                return jsonify({
                    "status": "error",
                    "message": sms_message,
                }), 502
            return jsonify({
                "status": "success",
                "id": letter_request.id,
                "verification_required": True,
                "phone_verification_sent": True,
                "phone_verified": False,
                "email_verified": False,
                "message": (
                    "Verification code sent to your phone. "
                    "Verify your phone before downloading the invitation letter."
                ),
            }), 200

        full_name = build_letter_invitee_full_name(
            payload["first_name"],
            payload["middle_name"],
            payload["last_name"],
            salutation,
        )
        invitee = {
            "full_name": full_name,
            "organization": payload["organization"],
            "address": payload["address"],
            "email": payload["email"],
        }
        return _send_event_letter_pdf(event, invitee, db)
    except RuntimeError as e:
        db.rollback()
        logger.exception("request_event_letter pdf: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        db.rollback()
        logger.exception("request_event_letter: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/public/<int:event_id>/letter/verify-phone", methods=["POST"])
def verify_event_letter_phone(event_id: int):
    """
    Verify phone and download the invitation letter PDF (no authentication).

    Body: { "id": 12, "verification_code": "123456" }
    """
    data = request.get_json(silent=True) or {}
    payload, validation_error = validate_phone_verification_payload(data, require_code=False)
    if validation_error:
        return jsonify({"status": "error", "message": validation_error}), 400

    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        if not event.is_published:
            return jsonify({"status": "error", "message": "Event is not available"}), 404

        if event.end_date < date.today():
            return jsonify({"status": "error", "message": "This event has already ended"}), 410

        letter_request = find_letter_request_by_id(db, event.id, payload["id"])
        if not letter_request:
            return jsonify({
                "status": "error",
                "message": "Letter request not found for this event",
            }), 404

        if not letter_request.phone_verified:
            if not payload.get("verification_code"):
                return jsonify({
                    "status": "error",
                    "message": "verification_code must be a 6-digit number",
                }), 400
            if not verification_codes_match(
                letter_request.phone_verification_code,
                payload["verification_code"],
            ):
                return jsonify({
                    "status": "error",
                    "message": "Invalid verification code",
                }), 400
            letter_request.phone_verified = True
            db.commit()

        salutation, salutation_error = get_salutation_or_error(db, letter_request.salutation_id)
        if salutation_error:
            return jsonify({"status": "error", "message": salutation_error}), 400

        invitee = build_invitee_from_letter_request(letter_request, salutation)
        return _send_event_letter_pdf(event, invitee, db)
    except RuntimeError as e:
        db.rollback()
        logger.exception("verify_event_letter_phone pdf: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        db.rollback()
        logger.exception("verify_event_letter_phone: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>", methods=["PUT"])
@jwt_required()
def update_event(event_id: int):
    """Update an event (admin). Supports partial updates including is_published and trainer_ids."""
    data = _flatten_event_input(request.get_json(silent=True) or {})
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        if any(k in data for k in ("title", "course_title", "venue", "start_date", "end_date")):
            base = _event_to_dict(event, db)
            base_flat = _flatten_event_input(base)
            merged = {**base_flat, **data}
            error = _apply_create_fields(event, merged)
            if error:
                return jsonify({"status": "error", "message": error}), 400
        else:
            if "course_description" in data:
                event.course_description = (data["course_description"] or "").strip() or None
            if "learning_outcomes" in data:
                event.learning_outcomes = (data["learning_outcomes"] or "").strip() or None
            if "start_date" in data:
                event.start_date = _parse_date(data["start_date"], "start_date")
            if "end_date" in data:
                event.end_date = _parse_date(data["end_date"], "end_date")
            if "start_time" in data:
                event.start_time = _parse_time_optional(data.get("start_time"))
            if "end_time" in data:
                event.end_time = _parse_time_optional(data.get("end_time"))
            if event.end_date < event.start_date:
                return jsonify({"status": "error", "message": "end_date must be on or after start_date"}), 400

        _apply_payment_fields(event, data)

        if "trainer_ids" in data:
            _assign_trainers(db, event, data.get("trainer_ids") or [])

        publish_error = None
        if "is_published" in data:
            if _parse_bool(data["is_published"]):
                publish_error = _try_publish_event(event, db)
            else:
                event.is_published = False

        event.updated_by = user_id
        event.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(event)

        response_message = "Event updated"
        if "is_published" in data and _parse_bool(data["is_published"]) and publish_error:
            response_message = f"Event saved but not published — {publish_error}"

        return jsonify({
            "status": "success",
            "message": response_message,
            "data": _event_to_dict(event, db),
            "published": bool(event.is_published),
        })
    except ValueError as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("update_event: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Trainers (shared invitation_trainers table)
# ---------------------------------------------------------------------------


def _parse_trainer_payload():
    if request.content_type and "multipart/form-data" in request.content_type:
        return {
            "full_name": request.form.get("full_name"),
            "designation": request.form.get("designation"),
            "bio": request.form.get("bio"),
            "qualifications": request.form.get("qualifications"),
            "is_active": request.form.get("is_active"),
        }, request.files.get("photo")
    data = request.get_json(silent=True) or {}
    return data, None


@events_bp.route("/api/events/trainers", methods=["GET"])
@jwt_required()
def list_event_trainers():
    """List trainers available for events."""
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
        logger.exception("list_event_trainers: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/trainers/<int:trainer_id>", methods=["GET"])
@jwt_required()
def get_event_trainer(trainer_id: int):
    db = get_db()
    try:
        trainer = db.query(InvitationTrainer).filter(InvitationTrainer.id == trainer_id).first()
        if not trainer:
            return jsonify({"status": "error", "message": "Trainer not found"}), 404
        return jsonify({"status": "success", "data": _trainer_to_dict(trainer)})
    except Exception as e:
        logger.exception("get_event_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/trainers", methods=["POST"])
@jwt_required()
def create_event_trainer():
    """Create a trainer profile for use on events."""
    data, photo_file = _parse_trainer_payload()
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        if not (data.get("full_name") or "").strip():
            return jsonify({"status": "error", "message": "full_name is required"}), 400

        photo_url = None
        if photo_file and photo_file.filename:
            photo_url = handle_invitation_trainer_photo_upload(
                photo_file, data.get("full_name") or ""
            )
        elif data.get("photo"):
            photo_url = data.get("photo")

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
        logger.exception("create_event_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/trainers/<int:trainer_id>", methods=["PUT"])
@jwt_required()
def update_event_trainer(trainer_id: int):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        trainer = db.query(InvitationTrainer).filter(InvitationTrainer.id == trainer_id).first()
        if not trainer:
            return jsonify({"status": "error", "message": "Trainer not found"}), 404

        data, photo_file = _parse_trainer_payload()
        if photo_file and photo_file.filename:
            photo_url = handle_invitation_trainer_photo_upload(
                photo_file, data.get("full_name") or trainer.full_name
            )
            if photo_url:
                trainer.photo = photo_url

        for field in ("full_name", "designation", "bio", "qualifications", "photo"):
            if field in data and data[field] is not None:
                value = data[field]
                if field != "photo":
                    value = str(value).strip() or None
                if field == "full_name" and value:
                    trainer.full_name = value
                elif field != "full_name":
                    setattr(trainer, field, value)
        if "is_active" in data:
            trainer.is_active = _parse_bool(data["is_active"])

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
        logger.exception("update_event_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/trainers/<int:trainer_id>", methods=["DELETE"])
@jwt_required()
def delete_event_trainer(trainer_id: int):
    """Soft-deactivate a trainer (sets is_active = false)."""
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
        logger.exception("delete_event_trainer: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@events_bp.route("/api/events/<int:event_id>/template", methods=["POST"])
@jwt_required()
def upload_event_template(event_id: int):
    """Upload or replace the HTML invitation template for an event (admin)."""
    db = get_db()
    try:
        event, err = _get_event_or_404(db, event_id)
        if err:
            return err

        file_storage = request.files.get("template")
        template_error = validate_html_template_upload(file_storage)
        if template_error:
            return jsonify({"status": "error", "message": template_error}), 400

        delete_invitation_template_file(event.invitation_template_path)
        path, filename = save_invitation_template(event.id, file_storage)
        event.invitation_template_path = path
        event.invitation_template_filename = filename
        event.updated_by = int(get_jwt_identity())
        event.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(event)

        return jsonify({
            "status": "success",
            "message": "Event template uploaded",
            "data": _event_to_dict(event, db),
        })
    except Exception as e:
        db.rollback()
        logger.exception("upload_event_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()
