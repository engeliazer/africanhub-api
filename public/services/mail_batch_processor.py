"""
Rate-limited mail batch processing (no Celery dependency).
"""

import logging
import threading
import time
from datetime import datetime

from database.db_connector import SessionLocal
from applications.models.models import (
    MailBatch,
    MailBatchRecipient,
    MailBatchStatus,
    MailRecipientStatus,
)
from public.services.mail_service import personalize_message, send_batch_email

logger = logging.getLogger(__name__)

_active_batch_ids: set[int] = set()
_active_batches_lock = threading.Lock()


def _clear_stale_pending_state(session, batch_id: int) -> None:
    """Clear processed_at/error_message on PENDING rows left from interrupted runs."""
    (
        session.query(MailBatchRecipient)
        .filter(
            MailBatchRecipient.batch_id == batch_id,
            MailBatchRecipient.status == MailRecipientStatus.pending,
        )
        .update(
            {
                MailBatchRecipient.processed_at: None,
                MailBatchRecipient.error_message: None,
            },
            synchronize_session=False,
        )
    )
    session.commit()


def process_mail_batch(batch_id: int) -> None:
    """Send all pending recipients in a batch with interval throttling."""
    logger.info("Starting mail batch processing for batch_id=%s", batch_id)
    session = SessionLocal()
    try:
        batch = session.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            logger.error("Mail batch %s not found", batch_id)
            return

        if batch.status != MailBatchStatus.processing:
            logger.warning("Mail batch %s is not PROCESSING (status=%s)", batch_id, batch.status)
            return

        _clear_stale_pending_state(session, batch_id)

        while True:
            pending = (
                session.query(MailBatchRecipient)
                .filter(
                    MailBatchRecipient.batch_id == batch_id,
                    MailBatchRecipient.status == MailRecipientStatus.pending,
                )
                .order_by(MailBatchRecipient.id)
                .limit(batch.interval_limit)
                .all()
            )
            if not pending:
                break

            for recipient in pending:
                body = personalize_message(batch.message_body, recipient.full_name)
                ok, err = send_batch_email(
                    from_email=batch.source_email,
                    to_email=recipient.email,
                    subject=batch.subject,
                    body=body,
                    attachment_path=batch.attachment_path,
                    attachment_filename=batch.attachment_filename,
                )
                recipient.status = (
                    MailRecipientStatus.processed if ok else MailRecipientStatus.failed
                )
                recipient.error_message = None if ok else err
                recipient.processed_at = datetime.utcnow()
                recipient.updated_at = datetime.utcnow()
                session.commit()
                logger.info(
                    "Mail batch %s recipient %s (%s): %s",
                    batch_id,
                    recipient.id,
                    recipient.email,
                    recipient.status.value,
                )

            remaining = (
                session.query(MailBatchRecipient)
                .filter(
                    MailBatchRecipient.batch_id == batch_id,
                    MailBatchRecipient.status == MailRecipientStatus.pending,
                )
                .count()
            )
            if remaining > 0 and batch.interval_seconds > 0:
                time.sleep(batch.interval_seconds)

        batch.status = MailBatchStatus.completed
        batch.completed_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        session.commit()
        logger.info("Mail batch %s completed", batch_id)
    except Exception:
        session.rollback()
        logger.exception("Mail batch %s processing failed", batch_id)
        raise
    finally:
        session.close()
        with _active_batches_lock:
            _active_batch_ids.discard(batch_id)


def _run_mail_batch_safe(batch_id: int) -> None:
    try:
        process_mail_batch(batch_id)
    except Exception:
        logger.exception("Background mail batch %s terminated with error", batch_id)


def start_mail_batch_background(batch_id: int) -> bool:
    """
    Run batch processing in a non-daemon thread so Gunicorn does not kill it
    when the HTTP request finishes. Returns False if already running in this worker.
    """
    with _active_batches_lock:
        if batch_id in _active_batch_ids:
            logger.warning("Mail batch %s is already processing in this worker", batch_id)
            return False
        _active_batch_ids.add(batch_id)

    thread = threading.Thread(
        target=_run_mail_batch_safe,
        args=(batch_id,),
        daemon=False,
        name=f"mail-batch-{batch_id}",
    )
    thread.start()
    logger.info("Mail batch %s background thread started (tid=%s)", batch_id, thread.ident)
    return True
