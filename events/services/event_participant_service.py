import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from auth.models.models import User
from certificates.models.models import Salutation
from certificates.services.participant_service import (
    format_user_full_name,
    get_salutation_by_id,
    get_salutation_for_user,
    get_user_or_error,
)
from events.models.models import Event, EventParticipant

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_guest_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def get_event_or_error(db: Session, event_id: int) -> Tuple[Optional[Event], Optional[str]]:
    row = db.query(Event).filter(Event.id == event_id).first()
    if not row:
        return None, "Event not found"
    return row, None


def get_salutation_or_error(
    db: Session,
    salutation_id: Optional[int],
) -> Tuple[Optional[Salutation], Optional[str]]:
    if salutation_id is None:
        return None, None
    row = get_salutation_by_id(db, salutation_id)
    if not row:
        return None, f"Salutation {salutation_id} not found or inactive"
    return row, None


def validate_email(email: Optional[str]) -> Optional[str]:
    if email in (None, ""):
        return None
    normalized = email.strip()
    if not EMAIL_RE.match(normalized):
        return "Invalid email address"
    return None


def participant_display_names(
    participant: EventParticipant,
    user: Optional[User],
    salutation: Optional[Salutation],
) -> Tuple[str, str]:
    if participant.user_id is not None and user is not None:
        core_name = format_user_full_name(user, None)
        display_name = format_user_full_name(user, salutation)
        return core_name, display_name

    core_name = (participant.full_name or "").strip()
    if salutation and salutation.label and salutation.label.lower() != "none":
        display_name = f"{salutation.label} {core_name}".strip()
    else:
        display_name = core_name
    return core_name, display_name


def existing_user_ids(db: Session, event_id: int) -> Set[int]:
    rows = (
        db.query(EventParticipant.user_id)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id.isnot(None),
            EventParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return {row[0] for row in rows}


def existing_guest_keys(db: Session, event_id: int) -> Set[Tuple[str, Optional[int]]]:
    rows = (
        db.query(EventParticipant.full_name, EventParticipant.salutation_id)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id.is_(None),
            EventParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return {(normalize_guest_name(name), salutation_id) for name, salutation_id in rows}


def build_participant_view(db: Session, participant: EventParticipant) -> Dict[str, Any]:
    from events.models.schemas import event_participant_payload

    user = None
    salutation = None
    if participant.user_id is not None:
        user, _ = get_user_or_error(db, participant.user_id)
        salutation = get_salutation_for_user(db, user) if user else None
    else:
        salutation, _ = get_salutation_or_error(db, participant.salutation_id)

    core_name, display_name = participant_display_names(participant, user, salutation)
    return event_participant_payload(
        participant,
        user=user,
        salutation=salutation,
        display_full_name=display_name,
        core_name=core_name,
    )


def create_participant_row(
    db: Session,
    event_id: int,
    data: Dict[str, Any],
    current_user_id: int,
    *,
    seen_user_ids: Set[int],
    seen_guest_keys: Set[Tuple[str, Optional[int]]],
) -> Tuple[Optional[EventParticipant], Optional[str]]:
    user_id = data.get("user_id")
    full_name = data.get("full_name")

    email_error = validate_email(data.get("email"))
    if email_error:
        return None, email_error

    if user_id is not None:
        if user_id in seen_user_ids:
            return None, f"User {user_id} is already on this event roster"
        _, user_error = get_user_or_error(db, user_id)
        if user_error:
            return None, user_error

        row = EventParticipant(
            event_id=event_id,
            user_id=user_id,
            organization=_optional_text(data.get("organization")),
            email=_optional_text(data.get("email")),
            phone=_optional_text(data.get("phone")),
            notes=_optional_text(data.get("notes")),
            created_by=current_user_id,
            updated_by=current_user_id,
        )
        seen_user_ids.add(user_id)
        return row, None

    salutation_id = data.get("salutation_id")
    _, salutation_error = get_salutation_or_error(db, salutation_id)
    if salutation_error:
        return None, salutation_error

    guest_key = (normalize_guest_name(full_name), salutation_id)
    if guest_key in seen_guest_keys:
        label = full_name
        return None, f"Walk-in participant '{label}' is already on this event roster"

    row = EventParticipant(
        event_id=event_id,
        full_name=full_name.strip(),
        salutation_id=salutation_id,
        organization=_optional_text(data.get("organization")),
        email=_optional_text(data.get("email")),
        phone=_optional_text(data.get("phone")),
        notes=_optional_text(data.get("notes")),
        created_by=current_user_id,
        updated_by=current_user_id,
    )
    seen_guest_keys.add(guest_key)
    return row, None


def _optional_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def list_event_participants(
    db: Session,
    event_id: int,
    *,
    participant_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.deleted_at.is_(None),
        )
        .order_by(EventParticipant.id.asc())
    )
    if participant_type == "walk_in":
        query = query.filter(EventParticipant.user_id.is_(None))
    elif participant_type == "user":
        query = query.filter(EventParticipant.user_id.isnot(None))

    rows = query.all()
    views = [build_participant_view(db, row) for row in rows]
    views.sort(key=lambda item: (item.get("full_name") or "").lower())
    return views
