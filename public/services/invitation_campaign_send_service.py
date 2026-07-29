"""
Send a single invitation campaign email with personalized PDF attachment.
"""

import logging
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from applications.models.models import (
    Invitation,
    InvitationEmailLog,
    InvitationEmailLogStatus,
    InvitationInvitee,
    InviteeSendStatus,
    InviteeValidationStatus,
)
from public.services.invitation_campaign_pdf_service import (
    invitation_pdf_filename,
    render_invitation_pdf_bytes,
)
from public.services.invitation_html_service import invitee_dict_from_model
from public.services.mail_service import NAME_PLACEHOLDER, send_batch_email

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def personalize_text(text: str, full_name: str) -> str:
    return (text or "").replace(NAME_PLACEHOLDER, full_name or "")


def _to_plain_text(text: str) -> str:
    """Normalize invitation message body to plain text for email."""
    raw = _BR_RE.sub("\n", text or "")
    raw = _TAG_RE.sub("", raw)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"[ \t]+\n", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _build_plain_email_body(invitation: Invitation, full_name: str, pdf_filename: str) -> str:
    message = _to_plain_text(personalize_text(invitation.email_message, full_name))
    attachment_note = (
        f"Please find the formal invitation letter attached "
        f"({pdf_filename})."
    )
    if message:
        return f"{message}\n\n{attachment_note}\n"
    return (
        f"Dear {full_name or 'Sir/Madam'},\n\n"
        f"Please find attached your invitation letter.\n\n"
        f"{attachment_note}\n"
    )


def _write_temp_pdf(invitation_id: int, pdf_bytes: bytes, filename: str) -> Path:
    out_dir = Path(tempfile.gettempdir()) / "invitation_campaign_pdfs" / str(invitation_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{uuid.uuid4().hex}_{filename}"
    path.write_bytes(pdf_bytes)
    return path


def _delete_temp_pdf(path: Optional[str]) -> None:
    if not path:
        return
    file_path = Path(path)
    if file_path.is_file():
        file_path.unlink(missing_ok=True)


def send_invitation_email(
    invitation: Invitation,
    invitee_data: Dict[str, Any],
    *,
    to_email: Optional[str] = None,
    record_log: bool = True,
    update_invitee: Optional[InvitationInvitee] = None,
    session=None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Generate PDF and send invitation email as plain text + PDF attachment
    (no branded HTML wrapper — reduces Promotions / spam folder placement).

    Returns (success, error_message, pdf_filename).
    """
    full_name = invitee_data.get("full_name") or ""
    destination = (to_email or invitee_data.get("email") or "").strip()
    if not destination:
        return False, "Recipient email is required", None

    pdf_path = None
    pdf_filename = invitation_pdf_filename(full_name)
    now = datetime.utcnow()
    email_log = None

    try:
        pdf_bytes, pdf_filename = render_invitation_pdf_bytes(invitation, invitee_data)
        pdf_path = _write_temp_pdf(invitation.id, pdf_bytes, pdf_filename)

        body = _build_plain_email_body(invitation, full_name, pdf_filename)
        subject = personalize_text(invitation.email_subject, full_name)

        if record_log and session is not None and update_invitee is not None:
            email_log = InvitationEmailLog(
                invitation_id=invitation.id,
                invitee_id=update_invitee.id,
                email=destination,
                status=InvitationEmailLogStatus.sending,
                created_at=now,
                updated_at=now,
            )
            session.add(email_log)
            if update_invitee.send_status != InviteeSendStatus.sending:
                update_invitee.send_status = InviteeSendStatus.sending
                update_invitee.updated_at = now
            session.flush()

        ok, err = send_batch_email(
            from_email=invitation.source_email,
            to_email=destination,
            subject=subject,
            body=body,
            attachment_path=str(pdf_path),
            attachment_filename=pdf_filename,
            use_html=False,
        )

        if record_log and session is not None and update_invitee is not None:
            update_invitee.send_status = (
                InviteeSendStatus.sent if ok else InviteeSendStatus.failed
            )
            update_invitee.error_message = None if ok else err
            update_invitee.sent_at = now if ok else update_invitee.sent_at
            update_invitee.processed_at = now
            update_invitee.updated_at = now
            if email_log:
                email_log.status = (
                    InvitationEmailLogStatus.sent if ok else InvitationEmailLogStatus.failed
                )
                email_log.error_message = None if ok else err
                email_log.sent_at = now if ok else None
                email_log.updated_at = now

        return ok, err, pdf_filename
    except Exception as e:
        logger.exception(
            "Invitation send failed for invitation %s to %s",
            invitation.id,
            destination,
        )
        if record_log and session is not None and update_invitee is not None:
            update_invitee.send_status = InviteeSendStatus.failed
            update_invitee.error_message = str(e)
            update_invitee.processed_at = now
            update_invitee.updated_at = now
            if email_log:
                email_log.status = InvitationEmailLogStatus.failed
                email_log.error_message = str(e)
                email_log.updated_at = now
        return False, str(e), pdf_filename
    finally:
        _delete_temp_pdf(str(pdf_path) if pdf_path else None)


def send_test_invitation_email(
    invitation: Invitation,
    invitee_data: Dict[str, Any],
    test_email: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Send a one-off test email without updating invitee rows or email logs."""
    return send_invitation_email(
        invitation,
        invitee_data,
        to_email=test_email,
        record_log=False,
        update_invitee=None,
        session=None,
    )


def count_pending_valid_invitees(session, invitation_id: int, *, include_failed: bool = False) -> int:
    statuses = [InviteeSendStatus.pending]
    if include_failed:
        statuses.append(InviteeSendStatus.failed)

    return (
        session.query(InvitationInvitee)
        .filter(
            InvitationInvitee.invitation_id == invitation_id,
            InvitationInvitee.validation_status == InviteeValidationStatus.valid,
            InvitationInvitee.send_status.in_(statuses),
        )
        .count()
    )


def invitee_data_for_send(invitee: InvitationInvitee) -> Dict[str, Any]:
    return invitee_dict_from_model(invitee)
