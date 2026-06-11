"""
Rate-limited invitation campaign sending with per-invitee PDF generation.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import joinedload

from database.db_connector import SessionLocal
from applications.models.models import (
    Invitation,
    InvitationCampaignStatus,
    InvitationInvitee,
    InvitationTrainerAssignment,
    InviteeSendStatus,
    InviteeValidationStatus,
)
from public.services.invitation_campaign_send_service import (
    count_pending_valid_invitees,
    invitee_data_for_send,
    send_invitation_email,
)

logger = logging.getLogger(__name__)

_active_invitation_ids: set[int] = set()
_active_lock = threading.Lock()


def _load_invitation(session, invitation_id: int) -> Optional[Invitation]:
    return (
        session.query(Invitation)
        .options(
            joinedload(Invitation.trainer_assignments).joinedload(
                InvitationTrainerAssignment.trainer
            ),
        )
        .filter(Invitation.id == invitation_id)
        .first()
    )


def _clear_stale_sending_state(session, invitation_id: int) -> None:
    """Reset invitees stuck in SENDING from interrupted runs back to PENDING."""
    (
        session.query(InvitationInvitee)
        .filter(
            InvitationInvitee.invitation_id == invitation_id,
            InvitationInvitee.validation_status == InviteeValidationStatus.valid,
            InvitationInvitee.send_status == InviteeSendStatus.sending,
        )
        .update(
            {
                InvitationInvitee.send_status: InviteeSendStatus.pending,
                InvitationInvitee.error_message: None,
            },
            synchronize_session=False,
        )
    )
    session.commit()


def process_invitation_campaign(invitation_id: int, *, include_failed: bool = False) -> None:
    """Send all pending valid invitees for a campaign with interval throttling."""
    logger.info("Starting invitation campaign processing for id=%s", invitation_id)
    session = SessionLocal()
    try:
        invitation = _load_invitation(session, invitation_id)
        if not invitation:
            logger.error("Invitation campaign %s not found", invitation_id)
            return

        if invitation.status != InvitationCampaignStatus.processing:
            logger.warning(
                "Invitation %s is not PROCESSING (status=%s)",
                invitation_id,
                invitation.status,
            )
            return

        _clear_stale_sending_state(session, invitation_id)

        send_statuses = [InviteeSendStatus.pending]
        if include_failed:
            send_statuses.append(InviteeSendStatus.failed)

        while True:
            pending = (
                session.query(InvitationInvitee)
                .filter(
                    InvitationInvitee.invitation_id == invitation_id,
                    InvitationInvitee.validation_status == InviteeValidationStatus.valid,
                    InvitationInvitee.send_status.in_(send_statuses),
                )
                .order_by(InvitationInvitee.id)
                .limit(invitation.interval_limit)
                .all()
            )
            if not pending:
                break

            invitation = _load_invitation(session, invitation_id)
            if not invitation:
                break

            for invitee in pending:
                ok, err, _filename = send_invitation_email(
                    invitation,
                    invitee_data_for_send(invitee),
                    update_invitee=invitee,
                    session=session,
                    record_log=True,
                )
                session.commit()
                logger.info(
                    "Invitation %s invitee %s (%s): %s%s",
                    invitation_id,
                    invitee.id,
                    invitee.email,
                    "SENT" if ok else "FAILED",
                    f" — {err}" if err else "",
                )

            remaining = count_pending_valid_invitees(
                session,
                invitation_id,
                include_failed=include_failed,
            )
            if remaining > 0 and invitation.interval_seconds > 0:
                time.sleep(invitation.interval_seconds)

        invitation = _load_invitation(session, invitation_id)
        if invitation:
            invitation.status = InvitationCampaignStatus.completed
            invitation.completed_at = datetime.utcnow()
            invitation.updated_at = datetime.utcnow()
            session.commit()
            logger.info("Invitation campaign %s completed", invitation_id)
    except Exception:
        session.rollback()
        logger.exception("Invitation campaign %s processing failed", invitation_id)
        raise
    finally:
        session.close()
        with _active_lock:
            _active_invitation_ids.discard(invitation_id)


def _run_safe(invitation_id: int, include_failed: bool) -> None:
    try:
        process_invitation_campaign(invitation_id, include_failed=include_failed)
    except Exception:
        logger.exception(
            "Background invitation campaign %s terminated with error",
            invitation_id,
        )


def start_invitation_campaign_background(
    invitation_id: int,
    *,
    include_failed: bool = False,
) -> bool:
    with _active_lock:
        if invitation_id in _active_invitation_ids:
            logger.warning("Invitation campaign %s already processing", invitation_id)
            return False
        _active_invitation_ids.add(invitation_id)

    thread = threading.Thread(
        target=_run_safe,
        args=(invitation_id, include_failed),
        daemon=False,
        name=f"invitation-campaign-{invitation_id}",
    )
    thread.start()
    return True


def dispatch_due_scheduled_campaigns() -> int:
    """
    Start campaigns that are SCHEDULED and past their scheduled_at time.
    Returns the number of campaigns queued.
    """
    session = SessionLocal()
    queued = 0
    try:
        now = datetime.utcnow()
        due = (
            session.query(Invitation)
            .filter(
                Invitation.status == InvitationCampaignStatus.scheduled,
                Invitation.scheduled_at.isnot(None),
                Invitation.scheduled_at <= now,
            )
            .all()
        )
        for invitation in due:
            pending = count_pending_valid_invitees(session, invitation.id)
            if pending == 0:
                continue
            invitation.status = InvitationCampaignStatus.processing
            invitation.started_at = now
            invitation.updated_at = now
            session.commit()

            queued_async, _already_running = queue_invitation_campaign_processing(invitation.id)
            if queued_async or _already_running:
                queued += 1
        return queued
    finally:
        session.close()


def queue_invitation_campaign_processing(
    invitation_id: int,
    *,
    include_failed: bool = False,
) -> tuple:
    """Returns (queued_via_celery, already_running_in_worker)."""
    try:
        from tasks_invitation_campaign import process_invitation_campaign_task
        process_invitation_campaign_task.delay(invitation_id, include_failed=include_failed)
        return True, False
    except Exception as e:
        logger.warning(
            "Celery unavailable for invitation campaign %s: %s",
            invitation_id,
            e,
        )
        started = start_invitation_campaign_background(
            invitation_id,
            include_failed=include_failed,
        )
        return False, not started
