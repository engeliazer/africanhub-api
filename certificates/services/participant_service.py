from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session

from auth.models.models import User
from certificates.models.models import CertificateParticipant, CertificateTrainingContext, Salutation


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
