"""
Rate-limited invitation mail batch processing with per-recipient PDF generation.
"""

import logging
import threading
import time
from datetime import datetime

from database.db_connector import SessionLocal
from applications.models.models import (
    InvitationMailBatch,
    InvitationMailBatchRecipient,
    MailBatchStatus,
    MailRecipientStatus,
)
from public.services.invitation_pdf_service import delete_temp_pdf, generate_invitation_pdf
from public.services.mail_service import personalize_message, send_batch_email

logger = logging.getLogger(__name__)

_active_batch_ids: set[int] = set()
_active_batches_lock = threading.Lock()


def _clear_stale_pending_state(session, batch_id: int) -> None:
    (
        session.query(InvitationMailBatchRecipient)
        .filter(
            InvitationMailBatchRecipient.batch_id == batch_id,
            InvitationMailBatchRecipient.status == MailRecipientStatus.pending,
        )
        .update(
            {
                InvitationMailBatchRecipient.processed_at: None,
                InvitationMailBatchRecipient.error_message: None,
            },
            synchronize_session=False,
        )
    )
    session.commit()


def process_invitation_mail_batch(batch_id: int) -> None:
    logger.info("Starting invitation mail batch processing for batch_id=%s", batch_id)
    session = SessionLocal()
    try:
        batch = (
            session.query(InvitationMailBatch)
            .filter(InvitationMailBatch.id == batch_id)
            .first()
        )
        if not batch:
            logger.error("Invitation batch %s not found", batch_id)
            return

        if batch.status != MailBatchStatus.processing:
            logger.warning(
                "Invitation batch %s is not PROCESSING (status=%s)",
                batch_id,
                batch.status,
            )
            return

        _clear_stale_pending_state(session, batch_id)

        while True:
            pending = (
                session.query(InvitationMailBatchRecipient)
                .filter(
                    InvitationMailBatchRecipient.batch_id == batch_id,
                    InvitationMailBatchRecipient.status == MailRecipientStatus.pending,
                )
                .order_by(InvitationMailBatchRecipient.id)
                .limit(batch.interval_limit)
                .all()
            )
            if not pending:
                break

            for recipient in pending:
                pdf_path = None
                pdf_filename = None
                try:
                    pdf_path, pdf_filename = generate_invitation_pdf(
                        template_path=batch.invitation_template_path,
                        full_name=recipient.full_name,
                        address=recipient.address,
                        organization=recipient.organization,
                        batch_id=batch_id,
                        recipient_id=recipient.id,
                    )
                    body = personalize_message(batch.message_body, recipient.full_name)
                    ok, err = send_batch_email(
                        from_email=batch.source_email,
                        to_email=recipient.email,
                        subject=batch.subject,
                        body=body,
                        attachment_path=pdf_path,
                        attachment_filename=pdf_filename,
                    )
                    recipient.status = (
                        MailRecipientStatus.processed if ok else MailRecipientStatus.failed
                    )
                    recipient.error_message = None if ok else err
                except Exception as e:
                    logger.exception(
                        "Invitation send failed for recipient %s", recipient.id
                    )
                    recipient.status = MailRecipientStatus.failed
                    recipient.error_message = str(e)
                finally:
                    delete_temp_pdf(pdf_path)
                    recipient.processed_at = datetime.utcnow()
                    recipient.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(
                        "Invitation batch %s recipient %s (%s): %s",
                        batch_id,
                        recipient.id,
                        recipient.email,
                        recipient.status.value,
                    )

            remaining = (
                session.query(InvitationMailBatchRecipient)
                .filter(
                    InvitationMailBatchRecipient.batch_id == batch_id,
                    InvitationMailBatchRecipient.status == MailRecipientStatus.pending,
                )
                .count()
            )
            if remaining > 0 and batch.interval_seconds > 0:
                time.sleep(batch.interval_seconds)

        batch.status = MailBatchStatus.completed
        batch.completed_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        session.commit()
        logger.info("Invitation batch %s completed", batch_id)
    except Exception:
        session.rollback()
        logger.exception("Invitation batch %s processing failed", batch_id)
        raise
    finally:
        session.close()
        with _active_batches_lock:
            _active_batch_ids.discard(batch_id)


def _run_safe(batch_id: int) -> None:
    try:
        process_invitation_mail_batch(batch_id)
    except Exception:
        logger.exception("Background invitation batch %s terminated with error", batch_id)


def start_invitation_batch_background(batch_id: int) -> bool:
    with _active_batches_lock:
        if batch_id in _active_batch_ids:
            logger.warning("Invitation batch %s already processing", batch_id)
            return False
        _active_batch_ids.add(batch_id)

    thread = threading.Thread(
        target=_run_safe,
        args=(batch_id,),
        daemon=False,
        name=f"invitation-mail-batch-{batch_id}",
    )
    thread.start()
    return True
