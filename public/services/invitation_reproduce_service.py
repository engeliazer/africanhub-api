"""
Duplicate an invitation campaign for reuse (no invitees, no extra PDF attachment).
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from applications.models.models import (
    Invitation,
    InvitationCampaignStatus,
    InvitationTrainerAssignment,
)
from public.services.invitation_campaign_template_service import CAMPAIGN_TEMPLATE_DIR
from public.services.invitation_partner_logo_service import PARTNER_LOGO_DIR

logger = logging.getLogger(__name__)


def _copy_file_for_invitation(
    src_path: Optional[str],
    dest_root: Path,
    invitation_id: int,
    original_filename: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    if not src_path:
        return None, None
    src = Path(src_path)
    if not src.is_file():
        logger.warning("Reproduce: source file missing %s", src_path)
        return None, None

    safe_name = secure_filename(original_filename or src.name) or src.name
    dest_dir = dest_root / str(invitation_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}_{safe_name}"
    shutil.copy2(src, dest)
    return str(dest), original_filename or safe_name


def reproduce_invitation(
    db,
    source: Invitation,
    *,
    user_id: int,
    title: Optional[str] = None,
) -> Invitation:
    """
    Create a new DRAFT invitation copied from source.

    Copied: content, trainers, custom HTML template, partner logo.
    Not copied: invitees, email logs, additional PDF attachment, send schedule/state.
    """
    new_title = (title or "").strip() or f"Copy of {source.title}"

    clone = Invitation(
        title=new_title,
        event_id=source.event_id,
        course_title=source.course_title,
        course_description=source.course_description,
        venue=source.venue,
        start_date=source.start_date,
        end_date=source.end_date,
        start_time=source.start_time,
        end_time=source.end_time,
        learning_outcomes=source.learning_outcomes,
        why_attend_intro=source.why_attend_intro,
        why_attend_points=source.why_attend_points,
        who_attend_intro=source.who_attend_intro,
        who_attend_points=source.who_attend_points,
        investment_details=source.investment_details,
        payment_intro=source.payment_intro,
        reservation_details=source.reservation_details,
        refund_policy=source.refund_policy,
        how_to_register=source.how_to_register,
        has_training_partner=source.has_training_partner,
        partner_name=source.partner_name,
        partner_logo_path=None,
        partner_logo_filename=None,
        additional_attachment_path=None,
        additional_attachment_filename=None,
        source_email=source.source_email,
        email_subject=source.email_subject,
        email_message=source.email_message,
        course_fee=source.course_fee,
        deposit_amount=source.deposit_amount,
        reservation_deadline=source.reservation_deadline,
        bank_account_name=source.bank_account_name,
        bank_account_number=source.bank_account_number,
        bank_name=source.bank_name,
        interval_seconds=source.interval_seconds,
        interval_limit=source.interval_limit,
        invitation_template_path=None,
        invitation_template_filename=None,
        scheduled_at=None,
        status=InvitationCampaignStatus.draft,
        started_at=None,
        completed_at=None,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(clone)
    db.flush()

    template_path, template_name = _copy_file_for_invitation(
        source.invitation_template_path,
        CAMPAIGN_TEMPLATE_DIR,
        clone.id,
        source.invitation_template_filename,
    )
    clone.invitation_template_path = template_path
    clone.invitation_template_filename = template_name

    logo_path, logo_name = _copy_file_for_invitation(
        source.partner_logo_path,
        PARTNER_LOGO_DIR,
        clone.id,
        source.partner_logo_filename,
    )
    clone.partner_logo_path = logo_path
    clone.partner_logo_filename = logo_name

    ordered = sorted(
        source.trainer_assignments,
        key=lambda a: (a.display_order, a.id),
    )
    for assignment in ordered:
        db.add(
            InvitationTrainerAssignment(
                invitation_id=clone.id,
                trainer_id=assignment.trainer_id,
                display_order=assignment.display_order,
            )
        )

    db.flush()
    return clone


def load_invitation_for_reproduce(db, invitation_id: int) -> Optional[Invitation]:
    return (
        db.query(Invitation)
        .options(joinedload(Invitation.trainer_assignments))
        .filter(Invitation.id == invitation_id)
        .first()
    )
