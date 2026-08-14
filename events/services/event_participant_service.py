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
from events.services.phone_utils import normalize_phone

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


def find_user_by_phone(db: Session, phone: str) -> Optional[User]:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    last_nine = normalized[-9:]
    candidates = (
        db.query(User)
        .filter(User.phone.isnot(None), User.phone.like(f"%{last_nine}"))
        .all()
    )
    for user in candidates:
        if normalize_phone(user.phone) == normalized:
            return user
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


def existing_phones(db: Session, event_id: int) -> Set[str]:
    rows = (
        db.query(EventParticipant.phone)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return {row[0] for row in rows if row[0]}


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
    seen_phones: Set[str],
) -> Tuple[Optional[EventParticipant], Optional[str]]:
    phone = normalize_phone(data.get("phone") or "")
    if not phone:
        return None, "phone is required and must be a valid Tanzania mobile number"
    if phone in seen_phones:
        return None, f"Phone {phone} is already on this event roster"

    email_error = validate_email(data.get("email"))
    if email_error:
        return None, email_error

    user = find_user_by_phone(db, phone)
    if user is not None:
        row = EventParticipant(
            event_id=event_id,
            user_id=user.id,
            phone=phone,
            organization=_optional_text(data.get("organization")),
            email=_optional_text(data.get("email")) or _optional_text(user.email),
            notes=_optional_text(data.get("notes")),
            created_by=current_user_id,
            updated_by=current_user_id,
        )
        seen_phones.add(phone)
        return row, None

    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return None, (
            "full_name is required when phone is not registered to a system user"
        )

    salutation_id = data.get("salutation_id")
    _, salutation_error = get_salutation_or_error(db, salutation_id)
    if salutation_error:
        return None, salutation_error

    row = EventParticipant(
        event_id=event_id,
        full_name=full_name,
        salutation_id=salutation_id,
        phone=phone,
        organization=_optional_text(data.get("organization")),
        email=_optional_text(data.get("email")),
        notes=_optional_text(data.get("notes")),
        created_by=current_user_id,
        updated_by=current_user_id,
    )
    seen_phones.add(phone)
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
