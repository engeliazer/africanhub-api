"""
Celery task for rate-limited mail batch processing.
"""

import logging
import time
from datetime import datetime

from celery_config import celery
from database.db_connector import SessionLocal
from applications.models.models import (
    MailBatch,
    MailBatchRecipient,
    MailBatchStatus,
    MailRecipientStatus,
)
from public.services.mail_service import personalize_message, send_batch_email

logger = logging.getLogger(__name__)


def _process_batch(batch_id: int) -> None:
    session = SessionLocal()
    try:
        batch = session.query(MailBatch).filter(MailBatch.id == batch_id).first()
        if not batch:
            logger.error("Mail batch %s not found", batch_id)
            return

        if batch.status != MailBatchStatus.processing:
            logger.warning("Mail batch %s is not PROCESSING (status=%s)", batch_id, batch.status)
            return

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
                ok, _err = send_batch_email(
                    from_email=batch.source_email,
                    to_email=recipient.email,
                    subject=batch.subject,
                    body=body,
                )
                recipient.status = (
                    MailRecipientStatus.processed if ok else MailRecipientStatus.failed
                )
                recipient.processed_at = datetime.utcnow()
                recipient.updated_at = datetime.utcnow()
                session.commit()

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


@celery.task(name="tasks_mail.process_mail_batch", bind=True, max_retries=0)
def process_mail_batch(self, batch_id: int):
    """Send all pending recipients in a batch with interval throttling."""
    _process_batch(batch_id)
