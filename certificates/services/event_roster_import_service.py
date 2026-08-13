from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.services.participant_service import (
    format_guest_full_name,
    get_salutation_by_id,
    get_salutation_for_user,
    get_user_or_error,
    guest_already_on_roster,
    participant_already_on_roster,
)
from certificates.services.serial_no_service import assign_participant_serial_no
from events.models.models import EventParticipant
from events.services.event_participant_service import normalize_guest_name


def _guest_key(full_name: str, salutation_id: Optional[int]) -> Tuple[str, Optional[int]]:
    return normalize_guest_name(full_name), salutation_id


def existing_certificate_guest_keys(db: Session, context_id: int) -> Set[Tuple[str, Optional[int]]]:
    rows = (
        db.query(CertificateParticipant.full_name, CertificateParticipant.salutation_id)
        .filter(
            CertificateParticipant.training_context_id == context_id,
            CertificateParticipant.user_id.is_(None),
            CertificateParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return {_guest_key(name, salutation_id) for name, salutation_id in rows}


def import_event_participants_to_context(
    db: Session,
    context: CertificateTrainingContext,
    current_user_id: int,
) -> Tuple[List[CertificateParticipant], int, Optional[str]]:
    if context.training_type != "event":
        return [], 0, "Import is only supported for event training contexts"

    event_rows = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.event_id == context.training_id,
            EventParticipant.deleted_at.is_(None),
        )
        .order_by(EventParticipant.id.asc())
        .all()
    )

    seen_user_ids: Set[int] = set()
    seen_guest_keys = existing_certificate_guest_keys(db, context.id)
    created: List[CertificateParticipant] = []
    skipped = 0

    for event_row in event_rows:
        if event_row.user_id is not None:
            if event_row.user_id in seen_user_ids:
                skipped += 1
                continue
            if participant_already_on_roster(db, context.id, event_row.user_id):
                skipped += 1
                continue
            _, user_error = get_user_or_error(db, event_row.user_id)
            if user_error:
                return created, skipped, user_error

            row = CertificateParticipant(
                training_context_id=context.id,
                user_id=event_row.user_id,
                event_participant_id=event_row.id,
                created_by=current_user_id,
                updated_by=current_user_id,
            )
            seen_user_ids.add(event_row.user_id)
        else:
            core_name = (event_row.full_name or "").strip()
            if not core_name:
                skipped += 1
                continue
            guest_key = _guest_key(core_name, event_row.salutation_id)
            if guest_key in seen_guest_keys:
                skipped += 1
                continue

            row = CertificateParticipant(
                training_context_id=context.id,
                full_name=core_name,
                salutation_id=event_row.salutation_id,
                event_participant_id=event_row.id,
                created_by=current_user_id,
                updated_by=current_user_id,
            )
            seen_guest_keys.add(guest_key)

        db.add(row)
        db.flush()
        assign_participant_serial_no(row, context)
        created.append(row)

    return created, skipped, None
