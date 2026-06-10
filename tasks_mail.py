"""
Celery task wrapper for mail batch processing (worker only).
"""

from celery_config import celery
from public.services.mail_batch_processor import process_mail_batch as _process_mail_batch


@celery.task(name="tasks_mail.process_mail_batch", bind=True, max_retries=0)
def process_mail_batch(self, batch_id: int):
    """Send all pending recipients in a batch with interval throttling."""
    _process_mail_batch(batch_id)
