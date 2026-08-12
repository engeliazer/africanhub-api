from typing import Any, NamedTuple, Optional, Tuple

from sqlalchemy.orm import Session

from auth.models.models import User
from certificates.models.models import CertificateParticipant, CertificateTrainingContext, Salutation


class ParticipantIdentity(NamedTuple):
    display_name: str
    salutation: Optional[Salutation]
    qualifies_for_cpd_override: Optional[bool]
    user_id: Optional[int]
    source: str
    source_id: int


def is_guest_participant(participant: CertificateParticipant) -> bool:
    return participant.user_id is None


def get_salutation_for_participant(
    db: Session,
    participant: CertificateParticipant,
    user: Optional[User] = None,
) -> Optional[Salutation]:
    if is_guest_participant(participant):
        return get_salutation_by_id(db, participant.salutation_id)
    if user is not None:
        return get_salutation_for_user(db, user)
    return None


def format_guest_full_name(
    core_name: str,
    salutation: Optional[Salutation],
) -> str:
    name = (core_name or "").strip()
    if salutation and salutation.label and salutation.label.lower() != "none":
        return f"{salutation.label} {name}".strip()
    return name


def resolve_certificate_participant_identity(
    db: Session,
    participant: CertificateParticipant,
    context: CertificateTrainingContext,
) -> Tuple[Optional[ParticipantIdentity], Optional[str]]:
    if is_guest_participant(participant):
        if not participant.full_name:
            return None, "Guest participant is missing full_name"
        salutation = get_salutation_for_participant(db, participant)
        display_name = format_guest_full_name(participant.full_name, salutation)
        return ParticipantIdentity(
            display_name=display_name,
            salutation=salutation,
            qualifies_for_cpd_override=participant.qualifies_for_cpd_override,
            user_id=None,
            source="certificate",
            source_id=participant.id,
        ), None

    user, user_error = get_user_or_error(db, participant.user_id)
    if user_error:
        return None, user_error
    salutation = get_salutation_for_user(db, user)
    return ParticipantIdentity(
        display_name=format_user_full_name(user, salutation),
        salutation=salutation,
        qualifies_for_cpd_override=participant.qualifies_for_cpd_override,
        user_id=user.id,
        source="certificate",
        source_id=participant.id,
    ), None


def get_training_context_or_error(
    db: Session,
    context_id: int,
) -> Tuple[Optional[CertificateTrainingContext], Optional[str]]:
    row = (
        db.query(CertificateTrainingContext)
        .filter(
            CertificateTrainingContext.id == context_id,
            CertificateTrainingContext.deleted_at.is_(None),
        )
        .first()
    )
    if not row:
        return None, "Training context not found"
    return row, None


def get_user_or_error(db: Session, user_id: int) -> Tuple[Optional[User], Optional[str]]:
    row = (
        db.query(User)
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )
    if not row:
        return None, f"User {user_id} not found"
    return row, None


def get_salutation_by_id(db: Session, salutation_id: Optional[int]) -> Optional[Salutation]:
    if not salutation_id:
        return None
    return (
        db.query(Salutation)
        .filter(Salutation.id == salutation_id, Salutation.is_active == True)
        .first()
    )


def get_salutation_for_user(db: Session, user: User) -> Optional[Salutation]:
    return get_salutation_by_id(db, user.salutation_id)


def format_user_full_name(user: User, salutation: Optional[Salutation]) -> str:
    name_parts = [user.first_name]
    if user.middle_name:
        name_parts.append(user.middle_name)
    name_parts.append(user.last_name)
    core_name = " ".join(part.strip() for part in name_parts if part and part.strip())

    if salutation and salutation.label and salutation.label.lower() != "none":
        return f"{salutation.label} {core_name}".strip()
    return core_name


def compute_qualifies_for_cpd(
    salutation: Optional[Salutation],
    training_context: CertificateTrainingContext,
    override: Optional[bool] = None,
) -> bool:
    if override is not None:
        return override
    if not salutation:
        return False
    return bool(salutation.qualifies_for_cpd and (training_context.cpd_hours or 0) > 0)


def participant_already_on_roster(
    db: Session,
    context_id: int,
    user_id: int,
) -> bool:
    return (
        db.query(CertificateParticipant.id)
        .filter(
            CertificateParticipant.training_context_id == context_id,
            CertificateParticipant.user_id == user_id,
            CertificateParticipant.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def _normalize_guest_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _guest_roster_key(full_name: str, salutation_id: Optional[int]) -> Tuple[str, Optional[int]]:
    return _normalize_guest_name(full_name), salutation_id


def guest_already_on_roster(
    db: Session,
    context_id: int,
    full_name: str,
    salutation_id: Optional[int],
) -> bool:
    target_key = _guest_roster_key(full_name, salutation_id)
    rows = (
        db.query(CertificateParticipant.full_name, CertificateParticipant.salutation_id)
        .filter(
            CertificateParticipant.training_context_id == context_id,
            CertificateParticipant.user_id.is_(None),
            CertificateParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return any(_guest_roster_key(name, sid) == target_key for name, sid in rows)
