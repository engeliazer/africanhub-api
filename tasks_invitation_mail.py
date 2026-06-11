"""Celery task wrapper for invitation mail batch processing."""

from celery_config import celery
from public.services.invitation_mail_batch_processor import (
    process_invitation_mail_batch as _process_invitation_mail_batch,
)


@celery.task(name="tasks_invitation_mail.process_invitation_mail_batch", bind=True, max_retries=0)
def process_invitation_mail_batch(self, batch_id: int):
    _process_invitation_mail_batch(batch_id)
