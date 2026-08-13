from typing import Optional

from sqlalchemy.orm import Session

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.services.training_context_service import training_record


def resolve_training_serial_code(db: Session, context: CertificateTrainingContext) -> str:
    """EVENT for calendar events; subject.code or course.code otherwise."""
    training_type = (context.training_type or "").strip().lower()
    if training_type == "event":
        return "EVENT"

    record, _ = training_record(db, training_type, context.training_id)
    if record is not None:
        code = getattr(record, "code", None)
        if code and str(code).strip():
            return str(code).strip().upper()
    return training_type.upper()


def build_participant_serial_no(
    db: Session,
    context: CertificateTrainingContext,
    certificate_participant_id: int,
) -> str:
    """
    AHBT/DCRC/{EVENT|SUBJECT_CODE|COURSE_CODE}/{certificate_participant_id}
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
