import re
from typing import Optional

from sqlalchemy.orm import Session

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.services.training_context_service import training_record

_SERIAL_CODE_RE = re.compile(r"[^A-Z0-9-]+")


def _sanitize_serial_code(value: str, *, max_length: int = 24) -> str:
    normalized = _SERIAL_CODE_RE.sub("", (value or "").strip().upper())
    return normalized[:max_length] if normalized else ""


def _date_serial_code(context: CertificateTrainingContext) -> str:
    if context.start_date:
        return context.start_date.strftime("%m%y")
    return "0000"


def resolve_training_serial_code(db: Session, context: CertificateTrainingContext) -> str:
    """
    Middle segment of the serial — never a bare training-type label (EVENT/SUBJECT).

    - subject / course: entity code (e.g. EXCEL-ADV, CPA-2026)
    - event: training month+year (e.g. 0826 for Aug 2026), like legacy cert numbering
    - fallback: month+year from the training context dates
    """
    training_type = (context.training_type or "").strip().lower()

    if training_type in {"subject", "course"}:
        record, _ = training_record(db, training_type, context.training_id)
        if record is not None:
            code = _sanitize_serial_code(getattr(record, "code", "") or "")
            if code:
                return code

    if training_type == "event":
        return _date_serial_code(context)

    return _date_serial_code(context)


def build_participant_serial_no(
    db: Session,
    context: CertificateTrainingContext,
    certificate_participant_id: int,
) -> str:
    """
    AHBT/DCRC/{training_code}/{certificate_participant_id}

    training_code = subject/course code, or MMYY for events.
    """
    home_code = (context.home_code or "").strip()
    invited_code = (context.invited_code or context.home_code or "").strip()
    training_code = resolve_training_serial_code(db, context)
    return f"{home_code}/{invited_code}/{training_code}/{certificate_participant_id}"


def assign_participant_serial_no(
    db: Session,
    participant: CertificateParticipant,
    context: CertificateTrainingContext,
) -> str:
    if participant.id is None:
        raise ValueError("Participant must be flushed before assigning serial_no")
    if participant.serial_no:
        return participant.serial_no

    serial_no = build_participant_serial_no(db, context, participant.id)
    participant.serial_no = serial_no
    return serial_no


def participant_confirmation_error(participant: CertificateParticipant) -> Optional[str]:
    if (participant.confirmation_status or "").strip().lower() != "confirmed":
        return (
            "Participant must be confirmed on the certificate roster before "
            "preview or issuance"
        )
    if not participant.serial_no:
        return "Participant is missing serial_no"
    return None
