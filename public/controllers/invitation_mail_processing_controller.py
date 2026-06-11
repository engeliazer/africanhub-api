"""
Invitation mail batches with per-recipient customized PDF attachments.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from applications.models.models import (
    InvitationMailBatch,
    InvitationMailBatchRecipient,
    MailBatchStatus,
    MailRecipientStatus,
)
from database.db_connector import get_db
from public.services.invitation_template_service import (
    delete_invitation_template_file,
    save_invitation_template,
    validate_html_template_upload,
)

logger = logging.getLogger(__name__)

invitation_mail_processing_bp = Blueprint("invitation_mail_processing", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _batch_to_dict(batch: InvitationMailBatch, include_recipients: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": batch.id,
        "source_email": batch.source_email,
        "subject": batch.subject,
        "message_body": batch.message_body,
        "interval_seconds": batch.interval_seconds,
        "interval_limit": batch.interval_limit,
        "status": batch.status.value if batch.status else None,
        "has_template": bool(batch.invitation_template_path),
        "invitation_template_filename": batch.invitation_template_filename,
        "uses_default_template": not bool(batch.invitation_template_path),
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "started_at": batch.started_at.isoformat() if batch.started_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
    }
    if include_recipients:
        data["recipients"] = [_recipient_to_dict(r) for r in batch.recipients]
        data["recipient_counts"] = _recipient_counts(batch.recipients)
    return data


def _recipient_to_dict(recipient: InvitationMailBatchRecipient) -> Dict[str, Any]:
    return {
        "id": recipient.id,
        "email": recipient.email,
        "full_name": recipient.full_name,
        "address": recipient.address,
        "organization": recipient.organization,
        "status": recipient.status.value if recipient.status else None,
        "error_message": recipient.error_message,
        "created_at": recipient.created_at.isoformat() if recipient.created_at else None,
        "processed_at": recipient.processed_at.isoformat() if recipient.processed_at else None,
    }


def _recipient_counts(recipients: List[InvitationMailBatchRecipient]) -> Dict[str, int]:
    counts = {"PENDING": 0, "PROCESSED": 0, "FAILED": 0}
    for r in recipients:
        key = r.status.value if r.status else "PENDING"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _validate_create_payload(data: dict) -> Optional[str]:
    required = [
        "source_email",
        "subject",
        "message_body",
        "interval_seconds",
        "interval_limit",
        "recipients",
    ]
    for field in required:
        if data.get(field) in (None, ""):
            return f"Missing required field: {field}"

    if not EMAIL_RE.match(str(data["source_email"]).strip()):
        return "Invalid source_email"

    try:
        interval_seconds = int(data["interval_seconds"])
        interval_limit = int(data["interval_limit"])
    except (TypeError, ValueError):
        return "interval_seconds and interval_limit must be integers"

    if interval_seconds < 0:
        return "interval_seconds must be >= 0"
    if interval_limit < 1:
        return "interval_limit must be >= 1"

    recipients = data.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        return "recipients must be a non-empty array"

    for i, item in enumerate(recipients):
        if not isinstance(item, dict):
            return f"recipients[{i}] must be an object"
        email = (item.get("email") or "").strip()
        full_name = (item.get("full_name") or "").strip()
        address = (item.get("address") or "").strip()
        organization = (item.get("organization") or "").strip()
        if not all([email, full_name, address, organization]):
            return (
                f"recipients[{i}] requires email, full_name, address, and organization"
            )
        if not EMAIL_RE.match(email):
            return f"recipients[{i}] has invalid email"

    return None


def _require_pending_batch(batch: InvitationMailBatch):
    if batch.status != MailBatchStatus.pending:
        return jsonify({
            "status": "error",
            "message": (
                f"Template can only be changed while batch is PENDING "
                f"(current: {batch.status.value})"
            ),
        }), 400
    return None


@invitation_mail_processing_bp.route("/api/mail/invitation-batches", methods=["POST"])
@jwt_required()
def create_invitation_mail_batch():
    """
    Create an invitation batch. PDF attachments are generated per recipient on send.

    Body: {
      "source_email": "...",
      "subject": "...",
      "message_body": "Dear [NAME], ...",
      "interval_seconds": 10,
      "interval_limit": 5,
      "recipients": [{
        "email": "...",
        "full_name": "...",
        "address": "...",
        "organization": "..."
      }]
    }

    Optional: POST /api/mail/invitation-batches/{id}/template (HTML with
    [NAME], [ADDRESS], [ORGANIZATION]) before start. Uses built-in template if omitted.
    """
    data = request.get_json(silent=True) or {}
    error = _validate_create_payload(data)
    if error:
        return jsonify({"status": "error", "message": error}), 400

    user_id = get_jwt_identity()
    db = get_db()
    try:
        batch = InvitationMailBatch(
            source_email=data["source_email"].strip(),
            subject=data["subject"].strip(),
            message_body=data["message_body"],
            interval_seconds=int(data["interval_seconds"]),
            interval_limit=int(data["interval_limit"]),
            status=MailBatchStatus.pending,
            created_by=int(user_id) if user_id else None,
        )
        db.add(batch)
        db.flush()

        for item in data["recipients"]:
            db.add(
                InvitationMailBatchRecipient(
                    batch_id=batch.id,
                    email=item["email"].strip(),
                    full_name=item["full_name"].strip(),
                    address=item["address"].strip(),
                    organization=item["organization"].strip(),
                    status=MailRecipientStatus.pending,
                )
            )

        db.commit()
        db.refresh(batch)
        return jsonify({
            "status": "success",
            "message": "Invitation mail batch created",
            "data": _batch_to_dict(batch),
        }), 201
    except Exception as e:
        db.rollback()
        logger.exception("create_invitation_mail_batch: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitation_mail_processing_bp.route(
    "/api/mail/invitation-batches/<int:batch_id>/template", methods=["POST"]
)
@jwt_required()
def upload_invitation_template(batch_id: int):
    """
    Upload custom HTML invitation template (PENDING batches only).

    multipart/form-data field: template (HTML file)

    Required placeholders in template: [NAME], [ADDRESS], [ORGANIZATION]
    """
    db = get_db()
    try:
        batch = db.query(InvitationMailBatch).filter(InvitationMailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Invitation batch not found"}), 404

        blocked = _require_pending_batch(batch)
        if blocked:
            return blocked

        file_storage = request.files.get("template")
        template_error = validate_html_template_upload(file_storage)
        if template_error:
            return jsonify({"status": "error", "message": template_error}), 400

        delete_invitation_template_file(batch.invitation_template_path)
        path, filename = save_invitation_template(batch.id, file_storage)
        batch.invitation_template_path = path
        batch.invitation_template_filename = filename
        batch.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(batch)

        return jsonify({
            "status": "success",
            "message": "Invitation template uploaded",
            "data": _batch_to_dict(batch, include_recipients=False),
        })
    except Exception as e:
        db.rollback()
        logger.exception("upload_invitation_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitation_mail_processing_bp.route(
    "/api/mail/invitation-batches/<int:batch_id>/template", methods=["DELETE"]
)
@jwt_required()
def remove_invitation_template(batch_id: int):
    """Remove custom template; batch will use built-in default on send."""
    db = get_db()
    try:
        batch = db.query(InvitationMailBatch).filter(InvitationMailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Invitation batch not found"}), 404

        blocked = _require_pending_batch(batch)
        if blocked:
            return blocked

        if not batch.invitation_template_path:
            return jsonify({"status": "error", "message": "No custom template on this batch"}), 404

        delete_invitation_template_file(batch.invitation_template_path)
        batch.invitation_template_path = None
        batch.invitation_template_filename = None
        batch.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(batch)

        return jsonify({
            "status": "success",
            "message": "Custom template removed; default template will be used",
            "data": _batch_to_dict(batch, include_recipients=False),
        })
    except Exception as e:
        db.rollback()
        logger.exception("remove_invitation_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitation_mail_processing_bp.route(
    "/api/mail/invitation-batches/<int:batch_id>/template", methods=["GET"]
)
@jwt_required()
def download_invitation_template(batch_id: int):
    """Download the custom HTML template for a batch."""
    db = get_db()
    try:
        batch = db.query(InvitationMailBatch).filter(InvitationMailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Invitation batch not found"}), 404
        if not batch.invitation_template_path or not Path(batch.invitation_template_path).is_file():
            return jsonify({
                "status": "error",
                "message": "No custom template; built-in default is used on send",
            }), 404
        return send_file(
            batch.invitation_template_path,
            mimetype="text/html",
            as_attachment=True,
            download_name=batch.invitation_template_filename or "invitation_template.html",
        )
    except Exception as e:
        logger.exception("download_invitation_template: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitation_mail_processing_bp.route(
    "/api/mail/invitation-batches/<int:batch_id>/start", methods=["POST"]
)
@jwt_required()
def start_invitation_mail_batch(batch_id: int):
    """Start or resume invitation sending (generates personalized PDF per recipient)."""
    db = get_db()
    try:
        batch = db.query(InvitationMailBatch).filter(InvitationMailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Invitation batch not found"}), 404

        if batch.status == MailBatchStatus.completed:
            return jsonify({"status": "error", "message": "Batch is already COMPLETED"}), 400

        pending_count = (
            db.query(InvitationMailBatchRecipient)
            .filter(
                InvitationMailBatchRecipient.batch_id == batch_id,
                InvitationMailBatchRecipient.status == MailRecipientStatus.pending,
            )
            .count()
        )
        if pending_count == 0:
            return jsonify({"status": "error", "message": "No pending recipients"}), 400

        resuming = batch.status == MailBatchStatus.processing
        if batch.status == MailBatchStatus.pending:
            batch.status = MailBatchStatus.processing
            batch.started_at = datetime.utcnow()
            batch.updated_at = datetime.utcnow()
            db.commit()

        from public.services.invitation_mail_batch_processor import (
            start_invitation_batch_background,
        )

        queued_async = False
        try:
            from tasks_invitation_mail import process_invitation_mail_batch as celery_task
            celery_task.delay(batch_id)
            queued_async = True
        except Exception as e:
            logger.warning("Celery unavailable for invitation batch: %s", e)
            if not start_invitation_batch_background(batch_id):
                return jsonify({
                    "status": "success",
                    "message": "Invitation batch is already processing",
                    "data": {
                        **_batch_to_dict(batch, include_recipients=False),
                        "queued_via_celery": False,
                        "resumed": resuming,
                        "already_running": True,
                    },
                })

        db.refresh(batch)
        return jsonify({
            "status": "success",
            "message": "Invitation batch resumed" if resuming else "Invitation batch started",
            "data": {
                **_batch_to_dict(batch, include_recipients=False),
                "queued_via_celery": queued_async,
                "resumed": resuming,
                "already_running": False,
            },
        })
    except Exception as e:
        db.rollback()
        logger.exception("start_invitation_mail_batch: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitation_mail_processing_bp.route("/api/mail/invitation-batches/<int:batch_id>", methods=["GET"])
@jwt_required()
def get_invitation_mail_batch(batch_id: int):
    db = get_db()
    try:
        batch = db.query(InvitationMailBatch).filter(InvitationMailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Invitation batch not found"}), 404
        return jsonify({"status": "success", "data": _batch_to_dict(batch)})
    except Exception as e:
        logger.exception("get_invitation_mail_batch: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@invitation_mail_processing_bp.route("/api/mail/invitation-batches", methods=["GET"])
@jwt_required()
def list_invitation_mail_batches():
    db = get_db()
    try:
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
        offset = (page - 1) * per_page

        q = db.query(InvitationMailBatch)
        total = q.count()
        batches = (
            q.order_by(InvitationMailBatch.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        return jsonify({
            "status": "success",
            "data": {
                "batches": [_batch_to_dict(b, include_recipients=False) for b in batches],
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page if total else 0,
                },
            },
        })
    except Exception as e:
        logger.exception("list_invitation_mail_batches: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()
