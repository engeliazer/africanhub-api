"""Celery task wrappers for full invitation campaign sending."""

from celery_config import celery
from public.services.invitation_campaign_processor import (
    dispatch_due_scheduled_campaigns as _dispatch_due,
    process_invitation_campaign as _process_invitation_campaign,
)


@celery.task(
    name="tasks_invitation_campaign.process_invitation_campaign_task",
    bind=True,
    max_retries=0,
)
def process_invitation_campaign_task(self, invitation_id: int, include_failed: bool = False):
    _process_invitation_campaign(invitation_id, include_failed=include_failed)


@celery.task(
    name="tasks_invitation_campaign.check_scheduled_invitation_campaigns",
    bind=True,
    max_retries=0,
)
def check_scheduled_invitation_campaigns(self):
    """Poll SCHEDULED campaigns whose scheduled_at has passed and start sending."""
    return _dispatch_due()
