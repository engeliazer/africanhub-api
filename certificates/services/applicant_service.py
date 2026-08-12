from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from applications.models.models import Application, ApplicationDetail, ApplicationStatus
from auth.models.models import User
from certificates.models.models import CertificateParticipant, CertificateTrainingContext, Salutation
from certificates.models.schemas import _format_user_full_name
from subjects.models.models import Subject


def get_subject_or_error(db: Session, subject_id: int) -> Tuple[Optional[Subject], Optional[str]]:
    row = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.deleted_at.is_(None))
        .first()
    )
    if not row:
        return None, "Subject not found"
    return row, None


def fetch_approved_applicants_for_subject(
    db: Session,
    subject_id: int,
) -> List[Tuple[ApplicationDetail, Application, User]]:
    return (
        db.query(ApplicationDetail, Application, User)
        .join(Application, ApplicationDetail.application_id == Application.id)
        .join(User, Application.user_id == User.id)
        .filter(
            ApplicationDetail.subject_id == subject_id,
            ApplicationDetail.deleted_at.is_(None),
            ApplicationDetail.is_active == True,
            ApplicationDetail.status == ApplicationStatus.approved,
            Application.deleted_at.is_(None),
            Application.is_active == True,
            Application.status == ApplicationStatus.approved,
            User.deleted_at.is_(None),
        )
        .order_by(User.last_name.asc(), User.first_name.asc())
        .all()
    )


def _salutation_map(db: Session, salutation_ids: Set[int]) -> Dict[int, Salutation]:
    if not salutation_ids:
        return {}
    rows = (
        db.query(Salutation)
        .filter(Salutation.id.in_(salutation_ids), Salutation.is_active == True)
        .all()
    )
    return {row.id: row for row in rows}


def roster_user_ids(db: Session, training_context_id: int) -> Set[int]:
    rows = (
        db.query(CertificateParticipant.user_id)
        .filter(
            CertificateParticipant.training_context_id == training_context_id,
            CertificateParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return {row[0] for row in rows}


def roster_user_ids_for_training(
    db: Session,
    training_type: str,
    training_id: int,
) -> Set[int]:
    """Users already on any certificate roster for this training source."""
    rows = (
        db.query(CertificateParticipant.user_id)
        .join(
            CertificateTrainingContext,
            CertificateParticipant.training_context_id == CertificateTrainingContext.id,
        )
        .filter(
            CertificateTrainingContext.training_type == training_type,
            CertificateTrainingContext.training_id == training_id,
            CertificateTrainingContext.deleted_at.is_(None),
            CertificateParticipant.deleted_at.is_(None),
        )
        .all()
    )
    return {row[0] for row in rows}


def resolve_assigned_user_ids(
    db: Session,
    training_type: str,
    training_id: int,
    training_context_id: Optional[int] = None,
) -> Set[int]:
    if training_context_id:
        return roster_user_ids(db, training_context_id)
    return roster_user_ids_for_training(db, training_type, training_id)


def parse_optional_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Boolean query param must be true or false")


def applicant_payload(
    detail: ApplicationDetail,
    application: Application,
    user: User,
    salutation: Optional[Salutation],
    *,
    already_on_roster: bool = False,
) -> Dict[str, Any]:
    return {
        "user_id": user.id,
        "full_name": _format_user_full_name(user, salutation),
        "salutation_id": user.salutation_id,
        "salutation": salutation.label if salutation else None,
        "email": user.email,
        "phone": user.phone,
        "application_id": application.id,
        "application_detail_id": detail.id,
        "application_status": application.status.value,
        "application_detail_status": detail.status.value,
        "already_on_roster": already_on_roster,
        "pending_certificate_assignment": not already_on_roster,
    }


def build_applicants_response(
    db: Session,
    subject: Subject,
    rows: List[Tuple[ApplicationDetail, Application, User]],
    *,
    training_type: str = "subject",
    training_id: Optional[int] = None,
    training_context_id: Optional[int] = None,
    pending_certificate_assignment: Optional[bool] = None,
    missing_salutation: Optional[bool] = None,
) -> Dict[str, Any]:
    seen_user_ids: Set[int] = set()
    applicants: List[Dict[str, Any]] = []
    total_before_filter = 0
    assigned_count = 0
    pending_count = 0
    missing_salutation_count = 0

    salutation_ids = {
        user.salutation_id for _, _, user in rows if user.salutation_id is not None
    }
    salutations = _salutation_map(db, salutation_ids)

    resolved_training_id = training_id if training_id is not None else subject.id
    on_roster = resolve_assigned_user_ids(
        db,
        training_type,
        resolved_training_id,
        training_context_id,
    )
    assignment_scope = "training_context" if training_context_id else training_type

    for detail, application, user in rows:
        if user.id in seen_user_ids:
            continue
        seen_user_ids.add(user.id)
        total_before_filter += 1

        is_assigned = user.id in on_roster
        if is_assigned:
            assigned_count += 1
        else:
            pending_count += 1

        has_salutation = user.salutation_id is not None
        if not has_salutation:
            missing_salutation_count += 1

        if pending_certificate_assignment is True and is_assigned:
            continue
        if pending_certificate_assignment is False and not is_assigned:
            continue
        if missing_salutation is True and has_salutation:
            continue
        if missing_salutation is False and not has_salutation:
            continue

        salutation = salutations.get(user.salutation_id) if user.salutation_id else None
        applicants.append(
            applicant_payload(
                detail,
                application,
                user,
                salutation,
                already_on_roster=is_assigned,
            )
        )

    return {
        "subject_id": subject.id,
        "subject_name": subject.name,
        "subject_code": subject.code,
        "training_type": training_type,
        "training_id": resolved_training_id,
        "training_context_id": training_context_id,
        "assignment_scope": assignment_scope,
        "filters": {
            "pending_certificate_assignment": pending_certificate_assignment,
            "missing_salutation": missing_salutation,
        },
        "summary": {
            "total_approved": total_before_filter,
            "already_assigned": assigned_count,
            "pending_assignment": pending_count,
            "missing_salutation": missing_salutation_count,
        },
        "count": len(applicants),
        "applicants": applicants,
    }
