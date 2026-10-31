"""Public access to special invitation PDFs through their linked event."""

import logging
import re
from io import BytesIO
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError

from applications.models.models import Invitation, InvitationCampaignStatus
from database.db_connector import get_db
from events.models.models import Event, EventTrainingRegistration
from public.services.invitation_campaign_pdf_service import render_invitation_pdf_bytes

logger = logging.getLogger(__name__)
public_invitations_bp = Blueprint("public_invitations", __name__)


def _self_invitee(data):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")
    limits = {
        "first_name": 100,
        "middle_name": 100,
        "last_name": 100,
        "address": 2000,
        "email": 255,
        "organization": 255,
        "phone": 50,
    }
    invitee = {}
    for field, limit in limits.items():
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required and must be a non-empty string")
        value = value.strip()
        if len(value) > limit:
            raise ValueError(f"{field} must be at most {limit} characters")
        invitee[field] = value
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", invitee["email"]):
        raise ValueError("Invalid email address")
    phone = re.sub(r"[\s().-]", "", invitee["phone"])
    if not re.fullmatch(r"\+?[0-9]{7,15}", phone):
        raise ValueError("Invalid phone number")
    invitee["phone"] = phone
    invitee["full_name"] = " ".join(invitee[key] for key in ("first_name", "middle_name", "last_name"))
    return invitee


def _public_invitation(db, event_id):
    event = db.query(Event).filter(Event.id == event_id, Event.is_published.is_(True)).first()
    if event is None:
        return None
    # Both public endpoints must resolve to the same campaign, even if the
    # newest campaign has no additional attachment.
    return (
        db.query(Invitation)
        .filter(
            Invitation.event_id == event_id,
            Invitation.status != InvitationCampaignStatus.cancelled,
        )
        .order_by(Invitation.id.desc())
        .first()
    )


@public_invitations_bp.route("/api/events/public/<int:event_id>/self-invitation", methods=["POST"])
def self_invitation(event_id):
    """Render the campaign letter with submitted details; no account or email send."""
    try:
        invitee = _self_invitee(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    db = get_db()
    try:
        invitation = _public_invitation(db, event_id)
        if invitation is None:
            return jsonify({"status": "error", "message": "Invitation not available for this event"}), 404
        pdf_bytes, filename = render_invitation_pdf_bytes(invitation, invitee)
        response = send_file(
            BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=False,
            download_name=filename, max_age=0,
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response
    except Exception:
        logger.exception("self_invitation failed for event %s", event_id)
        return jsonify({"status": "error", "message": "Unable to generate invitation PDF"}), 500
    finally:
        db.close()


@public_invitations_bp.route("/api/events/public/<int:event_id>/invitation/attachment", methods=["GET"])
def public_invitation_attachment(event_id):
    """View the additional campaign PDF inline, without authentication."""
    db = get_db()
    try:
        invitation = _public_invitation(db, event_id)
        if invitation is None:
            return jsonify({"status": "error", "message": "Invitation not available for this event"}), 404
        path = invitation.additional_attachment_path
        if not path or not Path(path).is_file():
            return jsonify({"status": "error", "message": "No attachment on this invitation"}), 404
        return send_file(
            str(Path(path).resolve()), mimetype="application/pdf", as_attachment=False,
            download_name=invitation.additional_attachment_filename or Path(path).name,
            max_age=0,
        )
    except Exception:
        logger.exception("public_invitation_attachment failed for event %s", event_id)
        return jsonify({"status": "error", "message": "Unable to load invitation attachment"}), 500
    finally:
        db.close()


@public_invitations_bp.route("/api/events/public/<int:event_id>/registrations", methods=["POST"])
def register_for_training(event_id):
    """Register a visitor for a published event; public submissions are pending."""
    try:
        details = _self_invitee(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    db = get_db()
    try:
        event = db.query(Event).filter(Event.id == event_id, Event.is_published.is_(True)).first()
        if event is None:
            return jsonify({"status": "error", "message": "Event is not available"}), 404
        registration = EventTrainingRegistration(
            event_id=event_id,
            first_name=details["first_name"],
            middle_name=details["middle_name"],
            last_name=details["last_name"],
            address=details["address"],
            email=details["email"].lower(),
            organization=details["organization"],
            phone=details["phone"],
            status="pending",
        )
        db.add(registration)
        db.commit()
        response = jsonify({
            "status": "success",
            "message": "Training registration received",
            "data": {"id": registration.id, "event_id": event_id, "status": registration.status},
        })
        response.headers["Cache-Control"] = "private, no-store"
        return response, 201
    except IntegrityError as exc:
        db.rollback()
        if "uq_event_training_registration_email" in str(exc.orig) or (
            "event_training_registrations.event_id, event_training_registrations.email" in str(exc.orig)
        ):
            return jsonify({"status": "error", "message": "This email is already registered for this event"}), 409
        logger.exception("Training registration integrity error for event %s", event_id)
        return jsonify({"status": "error", "message": "Unable to register for training"}), 500
    except Exception:
        db.rollback()
        logger.exception("Training registration failed for event %s", event_id)
        return jsonify({"status": "error", "message": "Unable to register for training"}), 500
    finally:
        db.close()
