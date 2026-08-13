from typing import Optional

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.services.certificate_renderer import format_cert_number


def build_participant_serial_no(
    context: CertificateTrainingContext,
    participant_id: int,
) -> str:
    """Build a unique serial from the training context pattern and roster row id."""
    return format_cert_number(
        context.cert_number_pattern,
        home_code=context.home_code,
        invited_code=context.invited_code,
        start_date=context.start_date,
        training_id=context.training_id,
        sequence=participant_id,
        preview=False,
    )


def assign_participant_serial_no(
    participant: CertificateParticipant,
    context: CertificateTrainingContext,
) -> str:
    if participant.id is None:
        raise ValueError("Participant must be flushed before assigning serial_no")
    if participant.serial_no:
        return participant.serial_no

    serial_no = build_participant_serial_no(context, participant.id)
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
