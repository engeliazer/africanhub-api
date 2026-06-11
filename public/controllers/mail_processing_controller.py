"""
Mail batch processing: create campaigns, start rate-limited sending, view status.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from applications.models.models import (
    MailBatch,
    MailBatchRecipient,
    MailBatchStatus,
    MailRecipientStatus,
)
from database.db_connector import get_db
from public.services.mail_attachment_service import (
    delete_batch_attachment_file,
    save_batch_pdf,
    validate_pdf_upload,
)

logger = logging.getLogger(__name__)

mail_processing_bp = Blueprint("mail_processing", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _batch_to_dict(batch: MailBatch, include_recipients: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": batch.id,
        "source_email": batch.source_email,
        "subject": batch.subject,
        "message_body": batch.message_body,
        "interval_seconds": batch.interval_seconds,
        "interval_limit": batch.interval_limit,
        "status": batch.status.value if batch.status else None,
        "has_attachment": bool(batch.attachment_path),
        "attachment_filename": batch.attachment_filename,
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


def _recipient_to_dict(recipient: MailBatchRecipient) -> Dict[str, Any]:
    return {
        "id": recipient.id,
        "email": recipient.email,
        "full_name": recipient.full_name,
        "status": recipient.status.value if recipient.status else None,
        "error_message": recipient.error_message,
        "created_at": recipient.created_at.isoformat() if recipient.created_at else None,
        "processed_at": recipient.processed_at.isoformat() if recipient.processed_at else None,
    }


def _recipient_counts(recipients: List[MailBatchRecipient]) -> Dict[str, int]:
    counts = {"PENDING": 0, "PROCESSED": 0, "FAILED": 0}
    for r in recipients:
        key = r.status.value if r.status else "PENDING"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _parse_recipients(raw) -> Optional[List[dict]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else None
        except json.JSONDecodeError:
            return None
    return None


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

    recipients = _parse_recipients(data.get("recipients"))
    if not recipients:
        return "recipients must be a non-empty array (or JSON string array for multipart)"

    for i, item in enumerate(recipients):
        if not isinstance(item, dict):
            return f"recipients[{i}] must be an object"
        email = (item.get("email") or "").strip()
        full_name = (item.get("full_name") or "").strip()
        if not email or not full_name:
            return f"recipients[{i}] requires email and full_name"
        if not EMAIL_RE.match(email):
            return f"recipients[{i}] has invalid email"

    data["recipients"] = recipients
    return None


@mail_processing_bp.route("/api/mail/batches", methods=["POST"])
@jwt_required()
def create_mail_batch():
    """
    Create a mail batch with recipients (all default status PENDING).

    JSON body:
    {
      "source_email": "...",
      "subject": "...",
      "message_body": "Dear [NAME], ...",
      "interval_seconds": 300,
      "interval_limit": 10,
      "recipients": [{"email": "...", "full_name": "..."}]
    }

    Optional PDF: POST /api/mail/batches/{id}/attachment before starting.
    """
    data = request.get_json(silent=True) or {}
    error = _validate_create_payload(data)
    if error:
        return jsonify({"status": "error", "message": error}), 400

    user_id = get_jwt_identity()
    db = get_db()
    try:
        batch = MailBatch(
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
                MailBatchRecipient(
                    batch_id=batch.id,
                    email=item["email"].strip(),
                    full_name=item["full_name"].strip(),
                    status=MailRecipientStatus.pending,
                )
            )

        db.commit()
        db.refresh(batch)
        return jsonify({
            "status": "success",
            "message": "Mail batch created",
            "data": _batch_to_dict(batch),
        }), 201
    except Exception as e:
        db.rollback()
        logger.exception("create_mail_batch: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


def _require_pending_batch_for_attachment(batch: MailBatch) -> Optional[tuple]:
    if batch.status != MailBatchStatus.pending:
        return jsonify({
            "status": "error",
            "message": (
                f"Attachment can only be changed while batch is PENDING "
                f"(current: {batch.status.value})"
            ),
        }), 400
    return None


@mail_processing_bp.route("/api/mail/batches/<int:batch_id>/attachment", methods=["POST"])
@jwt_required()
def upload_mail_batch_attachment(batch_id: int):
    """
    Upload or replace PDF attachment for a PENDING batch.

    multipart/form-data with field: attachment (PDF only, max 15MB)
    """
    db = get_db()
    try:
        batch = db.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Mail batch not found"}), 404

        blocked = _require_pending_batch_for_attachment(batch)
        if blocked:
            return blocked

        file_storage = request.files.get("attachment")
        pdf_error = validate_pdf_upload(file_storage, required=True)
        if pdf_error:
            return jsonify({"status": "error", "message": pdf_error}), 400

        delete_batch_attachment_file(batch.attachment_path)
        path, filename = save_batch_pdf(batch.id, file_storage)
        batch.attachment_path = path
        batch.attachment_filename = filename
        batch.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(batch)

        return jsonify({
            "status": "success",
            "message": "Attachment uploaded",
            "data": _batch_to_dict(batch, include_recipients=False),
        })
    except Exception as e:
        db.rollback()
        logger.exception("upload_mail_batch_attachment: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@mail_processing_bp.route("/api/mail/batches/<int:batch_id>/attachment", methods=["DELETE"])
@jwt_required()
def remove_mail_batch_attachment(batch_id: int):
    """Remove PDF attachment from a PENDING batch."""
    db = get_db()
    try:
        batch = db.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Mail batch not found"}), 404

        blocked = _require_pending_batch_for_attachment(batch)
        if blocked:
            return blocked

        if not batch.attachment_path:
            return jsonify({"status": "error", "message": "No attachment on this batch"}), 404

        delete_batch_attachment_file(batch.attachment_path)
        batch.attachment_path = None
        batch.attachment_filename = None
        batch.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(batch)

        return jsonify({
            "status": "success",
            "message": "Attachment removed",
            "data": _batch_to_dict(batch, include_recipients=False),
        })
    except Exception as e:
        db.rollback()
        logger.exception("remove_mail_batch_attachment: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@mail_processing_bp.route("/api/mail/batches/<int:batch_id>/attachment", methods=["GET"])
@jwt_required()
def download_mail_batch_attachment(batch_id: int):
    """Download the PDF attachment for a batch."""
    db = get_db()
    try:
        batch = db.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Mail batch not found"}), 404
        if not batch.attachment_path or not Path(batch.attachment_path).is_file():
            return jsonify({"status": "error", "message": "No attachment for this batch"}), 404
        return send_file(
            batch.attachment_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=batch.attachment_filename or "attachment.pdf",
        )
    except Exception as e:
        logger.exception("download_mail_batch_attachment: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@mail_processing_bp.route("/api/mail/batches/<int:batch_id>/start", methods=["POST"])
@jwt_required()
def start_mail_batch(batch_id: int):
    """Start or resume sending. Allowed when PENDING, or PROCESSING with pending recipients."""
    db = get_db()
    try:
        batch = db.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Mail batch not found"}), 404

        if batch.status == MailBatchStatus.completed:
            return jsonify({
                "status": "error",
                "message": "Batch is already COMPLETED",
            }), 400

        pending_count = (
            db.query(MailBatchRecipient)
            .filter(
                MailBatchRecipient.batch_id == batch_id,
                MailBatchRecipient.status == MailRecipientStatus.pending,
            )
            .count()
        )
        if pending_count == 0:
            return jsonify({"status": "error", "message": "No pending recipients in batch"}), 400

        resuming = batch.status == MailBatchStatus.processing
        if batch.status == MailBatchStatus.pending:
            batch.status = MailBatchStatus.processing
            batch.started_at = datetime.utcnow()
            batch.updated_at = datetime.utcnow()
            db.commit()

        from public.services.mail_batch_processor import start_mail_batch_background

        queued_async = False
        try:
            from tasks_mail import process_mail_batch as celery_process_mail_batch
            celery_process_mail_batch.delay(batch_id)
            queued_async = True
        except Exception as e:
            logger.warning("Celery unavailable, using background thread: %s", e)
            if not start_mail_batch_background(batch_id):
                return jsonify({
                    "status": "success",
                    "message": "Mail batch is already processing in this server worker",
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
            "message": "Mail batch processing resumed" if resuming else "Mail batch processing started",
            "data": {
                **_batch_to_dict(batch, include_recipients=False),
                "queued_via_celery": queued_async,
                "resumed": resuming,
                "already_running": False,
            },
        })
    except Exception as e:
        db.rollback()
        logger.exception("start_mail_batch: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@mail_processing_bp.route("/api/mail/batches/<int:batch_id>", methods=["GET"])
@jwt_required()
def get_mail_batch(batch_id: int):
    """Get batch details including recipient statuses."""
    db = get_db()
    try:
        batch = db.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            return jsonify({"status": "error", "message": "Mail batch not found"}), 404
        return jsonify({
            "status": "success",
            "data": _batch_to_dict(batch),
        })
    except Exception as e:
        logger.exception("get_mail_batch: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@mail_processing_bp.route("/api/mail/batches", methods=["GET"])
@jwt_required()
def list_mail_batches():
    """List mail batches (newest first)."""
    db = get_db()
    try:
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
        offset = (page - 1) * per_page

        q = db.query(MailBatch)
        total = q.count()
        batches = (
            q.order_by(MailBatch.created_at.desc())
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
        logger.exception("list_mail_batches: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()
