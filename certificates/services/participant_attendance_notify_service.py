from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.services.participant_service import resolve_certificate_participant_identity
from certificates.services.serial_no_service import assign_participant_serial_no
from events.models.models import EventParticipant
from public.controllers.sms_controller import SMSService

PROCESS_NAME = "certificate_attendance_notify"


def build_attendance_thank_you_message(full_name: str, serial_no: str) -> str:
    return (
        f"Dear {full_name},\n"
        f"Thank you for attending the course at African Hub. "
        f"Your attendance number is {serial_no}, you will need this to get your certificate."
    )


def resolve_certificate_participant_phone(
    db: Session,
    participant: CertificateParticipant,
) -> Optional[str]:
    if not participant.event_participant_id:
        return None

    event_participant = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.id == participant.event_participant_id,
            EventParticipant.deleted_at.is_(None),
        )
        .first()
    )
    if event_participant and event_participant.phone:
        return event_participant.phone

    return None


def _ensure_serial_no(
    db: Session,
    participant: CertificateParticipant,
    context: CertificateTrainingContext,
) -> Optional[str]:
    if participant.serial_no:
        return participant.serial_no
    if (participant.confirmation_status or "").strip().lower() != "confirmed":
        return None
    return assign_participant_serial_no(db, participant, context)


def notify_single_participant_attendance(
    db: Session,
    context: CertificateTrainingContext,
    participant: CertificateParticipant,
) -> Dict[str, Any]:
    participant_id = participant.id

    if (participant.confirmation_status or "").strip().lower() != "confirmed":
        return {
            "certificate_participant_id": participant_id,
            "status": "skipped",
            "reason": "Participant is not confirmed",
        }

    serial_no = _ensure_serial_no(db, participant, context)
    if not serial_no:
        return {
            "certificate_participant_id": participant_id,
            "status": "skipped",
            "reason": "Participant has no attendance number (serial_no)",
        }

    identity, identity_error = resolve_certificate_participant_identity(
        db,
        participant,
        context,
    )
    if identity_error or not identity:
        return {
            "certificate_participant_id": participant_id,
            "status": "skipped",
            "reason": identity_error or "Could not resolve participant name",
        }

    phone = resolve_certificate_participant_phone(db, participant)
    if not phone:
        return {
            "certificate_participant_id": participant_id,
            "status": "skipped",
            "reason": "No phone number on linked event participant",
            "full_name": identity.display_name,
            "serial_no": serial_no,
        }

    message = build_attendance_thank_you_message(identity.display_name, serial_no)
    result = SMSService.send_message(
        phone=phone,
        message=message,
        process_name=PROCESS_NAME,
    )
    if result.get("success"):
        return {
            "certificate_participant_id": participant_id,
            "status": "sent",
            "full_name": identity.display_name,
            "serial_no": serial_no,
            "phone": phone,
        }

    return {
        "certificate_participant_id": participant_id,
        "status": "failed",
        "reason": result.get("message") or "Failed to send SMS",
        "full_name": identity.display_name,
        "serial_no": serial_no,
        "phone": phone,
    }


def notify_context_participants_attendance(
    db: Session,
    context: CertificateTrainingContext,
    *,
    participant_ids: Optional[List[int]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    query = (
        db.query(CertificateParticipant)
        .filter(
            CertificateParticipant.training_context_id == context.id,
            CertificateParticipant.deleted_at.is_(None),
        )
        .order_by(CertificateParticipant.id.asc())
    )
    if participant_ids:
        query = query.filter(CertificateParticipant.id.in_(participant_ids))

    rows = query.all()
    found_ids = {row.id for row in rows}
    results = [
        notify_single_participant_attendance(db, context, row)
        for row in rows
    ]

    if participant_ids:
        for participant_id in participant_ids:
            if participant_id not in found_ids:
                results.append({
                    "certificate_participant_id": participant_id,
                    "status": "skipped",
                    "reason": "Participant not found in this training context",
                })

    counts = {"sent": 0, "skipped": 0, "failed": 0}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return results, counts
