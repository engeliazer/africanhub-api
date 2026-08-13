from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.models.schemas import ParticipantInput
from certificates.services.participant_service import (
    get_salutation_by_id,
    get_user_or_error,
    guest_already_on_roster,
    participant_already_on_roster,
)
from certificates.services.serial_no_service import assign_participant_serial_no
from certificates.services.training_context_service import normalize_training_type
from events.models.models import EventParticipant


def _training_id_from_item(item: ParticipantInput, training_type: str) -> Optional[int]:
    if training_type == "event":
        return item.event_id
    if training_type == "subject":
        return item.subject_id
    return item.course_id


def _validate_training_ref(
    item: ParticipantInput,
    context: CertificateTrainingContext,
) -> Tuple[str, int, Optional[str]]:
    training_type = normalize_training_type(item.type or context.training_type)
    training_id = _training_id_from_item(item, training_type)
    if training_id is None:
        training_id = context.training_id

    if training_type != context.training_type or training_id != context.training_id:
        return training_type, training_id, (
            f"Participant type/id must match this training context "
            f"({context.training_type} {context.training_id})"
        )
    return training_type, training_id, None


def _get_event_participant_or_error(
    db: Session,
    event_id: int,
    participant_id: int,
) -> Tuple[Optional[EventParticipant], Optional[str]]:
    row = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.id == participant_id,
            EventParticipant.event_id == event_id,
            EventParticipant.deleted_at.is_(None),
        )
        .first()
    )
    if not row:
        return None, f"Event participant {participant_id} not found for event {event_id}"
    return row, None


def event_participant_on_roster(
    db: Session,
    context_id: int,
    event_participant_id: int,
) -> bool:
    return (
        db.query(CertificateParticipant.id)
        .filter(
            CertificateParticipant.training_context_id == context_id,
            CertificateParticipant.event_participant_id == event_participant_id,
            CertificateParticipant.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def create_certificate_participant(
    db: Session,
    context: CertificateTrainingContext,
    item: ParticipantInput,
    current_user_id: int,
) -> Tuple[Optional[CertificateParticipant], Optional[str]]:
    training_type, training_id, ref_error = _validate_training_ref(item, context)
    if ref_error:
        return None, ref_error

    user_id = item.user_id
    full_name = (item.full_name or "").strip() or None
    salutation_id = item.salutation_id
    email = (item.email or "").strip() or None
    organization = (item.organization or "").strip() or None
    event_participant_id = None

    if training_type == "event" and item.participant_id is not None:
        event_row, event_error = _get_event_participant_or_error(
            db,
            training_id,
            item.participant_id,
        )
        if event_error:
            return None, event_error

        if event_participant_on_roster(db, context.id, event_row.id):
            return None, f"Event participant {event_row.id} is already on this roster"

        event_participant_id = event_row.id
        if user_id is None:
            user_id = event_row.user_id
        if not full_name:
            full_name = (event_row.full_name or "").strip() or None
        if salutation_id is None:
            salutation_id = event_row.salutation_id
        if not email:
            email = (event_row.email or "").strip() or None
        if not organization:
            organization = (event_row.organization or "").strip() or None

    if user_id is not None:
        _, user_error = get_user_or_error(db, user_id)
        if user_error:
            return None, user_error
        if participant_already_on_roster(db, context.id, user_id):
            return None, f"User {user_id} is already on this roster"
    else:
        if not full_name:
            return None, "full_name is required when user_id is not provided"
        if salutation_id is not None and not get_salutation_by_id(db, salutation_id):
            return None, f"Salutation {salutation_id} not found or inactive"
        if guest_already_on_roster(db, context.id, full_name, salutation_id):
            return None, f"Guest '{full_name}' is already on this roster"

    row = CertificateParticipant(
        training_context_id=context.id,
        user_id=user_id,
        full_name=full_name,
        salutation_id=salutation_id,
        event_participant_id=event_participant_id,
        email=email,
        organization=organization,
        created_by=current_user_id,
        updated_by=current_user_id,
    )
    db.add(row)
    db.flush()
    assign_participant_serial_no(db, row, context)
    return row, None
