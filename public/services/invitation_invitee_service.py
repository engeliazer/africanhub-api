"""
Invitee validation and persistence for invitation campaigns.
Frontend supplies parsed rows; Excel parsing is not handled here.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from applications.models.models import (
    Invitation,
    InvitationCampaignStatus,
    InvitationInvitee,
    InviteeSendStatus,
    InviteeValidationStatus,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_INVITEES_PER_REQUEST = 5000


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _normalize_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_invitee_rows(rows: List[dict]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Validate invitee rows without persisting.

    Returns (validated_rows, summary_counts).
    """
    if not isinstance(rows, list):
        raise ValueError("invitees must be an array")
    if not rows:
        raise ValueError("invitees must be a non-empty array")
    if len(rows) > MAX_INVITEES_PER_REQUEST:
        raise ValueError(f"invitees cannot exceed {MAX_INVITEES_PER_REQUEST} records per request")

    parsed: List[Dict[str, Any]] = []

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"invitees[{index}] must be an object")

        full_name = _normalize_text(row.get("full_name"))
        email_raw = _normalize_text(row.get("email"))
        address = _normalize_text(row.get("address"))
        organization = _normalize_text(row.get("organization"))
        email_norm = _normalize_email(email_raw) if email_raw else None

        parsed.append({
            "row_index": index,
            "full_name": full_name,
            "email": email_raw,
            "address": address,
            "organization": organization,
            "_email_norm": email_norm,
        })

    validated: List[Dict[str, Any]] = []
    summary = {"total": len(parsed), "valid": 0, "invalid": 0, "duplicate": 0}

    seen_valid_emails: set = set()

    for item in parsed:
        full_name = item["full_name"]
        email_raw = item["email"]
        email_norm = item["_email_norm"]
        row = {
            "row_index": item["row_index"],
            "full_name": full_name,
            "email": email_raw,
            "address": item["address"],
            "organization": item["organization"],
            "validation_status": InviteeValidationStatus.valid.value,
            "validation_message": None,
        }

        if not full_name:
            row["validation_status"] = InviteeValidationStatus.invalid.value
            row["validation_message"] = "Full name is required"
            summary["invalid"] += 1
        elif not email_raw:
            row["validation_status"] = InviteeValidationStatus.invalid.value
            row["validation_message"] = "Email is required"
            summary["invalid"] += 1
        elif not EMAIL_RE.match(email_raw):
            row["validation_status"] = InviteeValidationStatus.invalid.value
            row["validation_message"] = "Invalid email format"
            summary["invalid"] += 1
        elif email_norm in seen_valid_emails:
            row["validation_status"] = InviteeValidationStatus.duplicate.value
            row["validation_message"] = "Duplicate email in upload"
            row["email"] = email_raw
            summary["duplicate"] += 1
        else:
            row["email"] = email_norm
            seen_valid_emails.add(email_norm)
            summary["valid"] += 1

        validated.append(row)

    return validated, summary


def build_invitee_summary(invitees: List[InvitationInvitee]) -> Dict[str, int]:
    return {
        "total": len(invitees),
        "valid": sum(
            1 for i in invitees if i.validation_status == InviteeValidationStatus.valid
        ),
        "invalid": sum(
            1 for i in invitees if i.validation_status == InviteeValidationStatus.invalid
        ),
        "duplicate": sum(
            1 for i in invitees if i.validation_status == InviteeValidationStatus.duplicate
        ),
        "pending_send": sum(
            1 for i in invitees if i.send_status == InviteeSendStatus.pending
        ),
        "sent": sum(
            1 for i in invitees if i.send_status == InviteeSendStatus.sent
        ),
        "failed": sum(
            1 for i in invitees if i.send_status == InviteeSendStatus.failed
        ),
    }


def sync_invitation_invitees(
    db,
    invitation: Invitation,
    rows: List[dict],
    *,
    replace: bool = True,
    user_id: Optional[int] = None,
) -> Tuple[List[InvitationInvitee], Dict[str, int]]:
    """
    Validate and persist invitees for an invitation.
    Replaces existing invitees when replace=True.
    """
    validated_rows, summary = validate_invitee_rows(rows)

    if replace:
        db.query(InvitationInvitee).filter(
            InvitationInvitee.invitation_id == invitation.id
        ).delete(synchronize_session=False)
        db.flush()

    saved: List[InvitationInvitee] = []
    now = datetime.utcnow()

    for row in validated_rows:
        invitee = InvitationInvitee(
            invitation_id=invitation.id,
            full_name=row["full_name"] or "",
            email=row["email"] or "",
            address=row["address"],
            organization=row["organization"],
            validation_status=InviteeValidationStatus[row["validation_status"].lower()],
            validation_message=row["validation_message"],
            send_status=InviteeSendStatus.pending,
            created_at=now,
            updated_at=now,
        )
        db.add(invitee)
        saved.append(invitee)

    if summary["valid"] > 0:
        if invitation.status == InvitationCampaignStatus.draft:
            invitation.status = InvitationCampaignStatus.validated
    elif invitation.status == InvitationCampaignStatus.validated:
        invitation.status = InvitationCampaignStatus.draft

    if user_id is not None:
        invitation.updated_by = user_id
    invitation.updated_at = now

    db.flush()
    return saved, summary
