"""
Entitlement checks before issuing LMS content tokens.

Payment and enrollment logic lives here — the LMS trusts grants once issued.
"""

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from applications.models.models import (
    Application,
    ApplicationDetail,
    PaymentStatus,
    ApplicationStatus,
)
from auth.models.models import User, UserRole, Role
from books.models.models import BookSubjectLink, BookAccessGrantLog


ADMIN_ROLE_CODES = {"SUPADM", "SYSADMIN"}


def user_has_admin_role(db: Session, user_id: int) -> bool:
    role = (
        db.query(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id, UserRole.deleted_at.is_(None))
        .first()
    )
    return bool(role and role.code in ADMIN_ROLE_CODES)


def get_book_subject_link(db: Session, lms_book_id: int) -> Optional[BookSubjectLink]:
    return (
        db.query(BookSubjectLink)
        .filter(
            BookSubjectLink.lms_book_id == lms_book_id,
            BookSubjectLink.is_active.is_(True),
            BookSubjectLink.deleted_at.is_(None),
        )
        .first()
    )


def user_has_subject_entitlement(db: Session, user_id: int, subject_id: int) -> bool:
    blocked_statuses = {
        ApplicationStatus.rejected,
        ApplicationStatus.withdrawn,
    }

    entitlement = (
        db.query(ApplicationDetail.id)
        .join(Application, Application.id == ApplicationDetail.application_id)
        .filter(
            Application.user_id == user_id,
            Application.deleted_at.is_(None),
            Application.is_active.is_(True),
            Application.payment_status == PaymentStatus.paid,
            Application.status.notin_(blocked_statuses),
            ApplicationDetail.subject_id == subject_id,
            ApplicationDetail.deleted_at.is_(None),
            ApplicationDetail.is_active.is_(True),
        )
        .first()
    )
    return entitlement is not None


def check_book_access_entitlement(
    db: Session,
    user: User,
    lms_book_id: int,
) -> Tuple[bool, Optional[str]]:
    """
    Returns (allowed, denial_reason).
    Admins bypass entitlement checks for support/testing.
    """
    if user_has_admin_role(db, user.id):
        return True, None

    link = get_book_subject_link(db, lms_book_id)
    if not link:
        return False, "This book is not linked to a course subject"

    if not user_has_subject_entitlement(db, user.id, link.subject_id):
        return False, "You do not have an active paid enrollment for this book's course"

    return True, None


def record_grant_log(
    db: Session,
    user_id: int,
    lms_book_id: int,
    grant_payload: dict,
) -> BookAccessGrantLog:
    grant = grant_payload.get("grant") or {}
    log = BookAccessGrantLog(
        user_id=user_id,
        lms_book_id=lms_book_id,
        lms_grant_id=grant.get("id"),
        status=grant.get("status") or "active",
        issued_at=_parse_datetime(grant.get("issued_at")),
        expires_at=_parse_datetime(grant.get("expires_at")),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def mark_grant_revoked(db: Session, user_id: int, lms_book_id: int) -> None:
    logs = (
        db.query(BookAccessGrantLog)
        .filter(
            BookAccessGrantLog.user_id == user_id,
            BookAccessGrantLog.lms_book_id == lms_book_id,
            BookAccessGrantLog.status == "active",
        )
        .all()
    )
    now = datetime.utcnow()
    for log in logs:
        log.status = "revoked"
        log.revoked_at = now
    if logs:
        db.commit()


def revoke_book_access_for_subject(db: Session, user_id: int, subject_id: int) -> int:
    """
    Revoke LMS access for all books linked to a subject.
    Call from payment refund / subscription cancellation flows.
    Returns the number of book links processed.
    """
    from services.lms_client import get_lms_client, LMSClientError

    links = (
        db.query(BookSubjectLink)
        .filter(
            BookSubjectLink.subject_id == subject_id,
            BookSubjectLink.is_active.is_(True),
            BookSubjectLink.deleted_at.is_(None),
        )
        .all()
    )
    if not links:
        return 0

    client = get_lms_client()
    if not client:
        return 0

    user = db.query(User).get(user_id)
    if not user:
        return 0

    lms_user_id = str(user.id)
    count = 0
    for link in links:
        try:
            client.revoke_active_access(lms_user_id, link.lms_book_id)
            mark_grant_revoked(db, user_id, link.lms_book_id)
            count += 1
        except LMSClientError:
            continue
    return count


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
