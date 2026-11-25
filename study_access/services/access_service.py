"""Study periods and the check that decides when a student may open lessons."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from applications.models.models import Application, ApplicationDetail, ApplicationStatus
from auth.models.models import Role, UserRole
from studies.models.models import SubtopicMaterial
from study_access.models.models import StudyPeriod
from study_access.services.rules import (
    MAX_EXTENSIONS,
    PERIOD_EXTENSION,
    PERIOD_INITIAL,
    STUDY_PERIOD_ENDED,
    StudyAccessError,
    classify_study_window,
    expected_end_date,
    extension_start_date,
    extensions_remaining,
    root_application_id,
)
from subjects.models.models import Subject, SubTopic, Topic


STAFF_ROLE_CODES = {"SUPADM", "SYSADMIN", "FACILITATOR"}
CLOSED_APPLICATION_STATUSES = {
    ApplicationStatus.rejected.value,
    ApplicationStatus.withdrawn.value,
}


def _today() -> date:
    return datetime.utcnow().date()


def _status_value(value) -> Optional[str]:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _iso_date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _iso_datetime(value) -> Optional[str]:
    return value.isoformat() if value else None


def user_is_staff(db: Session, user_id: int) -> bool:
    rows = (
        db.query(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(
            UserRole.user_id == user_id,
            UserRole.deleted_at.is_(None),
            UserRole.is_active.is_(True),
        )
        .all()
    )
    return bool({row.code for row in rows} & STAFF_ROLE_CODES)


def subject_id_for_material(db: Session, material_id: int) -> Optional[int]:
    row = (
        db.query(Topic.subject_id)
        .join(SubTopic, SubTopic.topic_id == Topic.id)
        .join(SubtopicMaterial, SubtopicMaterial.subtopic_id == SubTopic.id)
        .filter(SubtopicMaterial.id == material_id)
        .first()
    )
    return row.subject_id if row else None


def _periods_query(db: Session, user_id: int, subject_id: int):
    return db.query(StudyPeriod).filter(
        StudyPeriod.user_id == user_id,
        StudyPeriod.subject_id == subject_id,
        StudyPeriod.deleted_at.is_(None),
        StudyPeriod.is_active.is_(True),
    )


def user_can_study(db: Session, user_id: int, subject_id: int, on_date: Optional[date] = None) -> bool:
    on_date = on_date or _today()
    row = (
        _periods_query(db, user_id, subject_id)
        .join(Application, Application.id == StudyPeriod.application_id)
        .filter(
            StudyPeriod.start_date <= on_date,
            StudyPeriod.expected_end_date >= on_date,
            Application.status == ApplicationStatus.approved,
            Application.is_active.is_(True),
            Application.deleted_at.is_(None),
        )
        .first()
    )
    return row is not None


def active_subject_ids(db: Session, user_id: int, on_date: Optional[date] = None) -> set:
    on_date = on_date or _today()
    rows = (
        db.query(StudyPeriod.subject_id)
        .join(Application, Application.id == StudyPeriod.application_id)
        .filter(
            StudyPeriod.user_id == user_id,
            StudyPeriod.deleted_at.is_(None),
            StudyPeriod.is_active.is_(True),
            StudyPeriod.start_date <= on_date,
            StudyPeriod.expected_end_date >= on_date,
            Application.status == ApplicationStatus.approved,
            Application.is_active.is_(True),
            Application.deleted_at.is_(None),
        )
        .distinct()
        .all()
    )
    return {row.subject_id for row in rows}


def material_block(db: Session, user_id: int, material_id: int) -> Optional[dict]:
    """Why this student cannot open the material, or None when access is allowed."""
    if user_is_staff(db, user_id):
        return None
    subject_id = subject_id_for_material(db, material_id)
    if subject_id is None:
        return None
    if user_can_study(db, user_id, subject_id):
        return None
    started = _periods_query(db, user_id, subject_id).first()
    if started:
        return {
            "code": STUDY_PERIOD_ENDED,
            "message": "Your study period has ended. Apply again to continue.",
        }
    return {
        "code": "study_not_started",
        "message": "Start studying to open this material.",
    }


def subject_has_study_period(db: Session, user_id: int, subject_id: int) -> bool:
    return _periods_query(db, user_id, subject_id).first() is not None


def application_already_logged(db: Session, application_id: int, subject_id: int) -> bool:
    return (
        db.query(StudyPeriod.id)
        .filter(
            StudyPeriod.application_id == application_id,
            StudyPeriod.subject_id == subject_id,
            StudyPeriod.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def open_application_for_subject(db: Session, user_id: int, subject_id: int):
    """An application for this subject that is not closed and has no study row yet."""
    details = (
        db.query(ApplicationDetail, Application)
        .join(Application, Application.id == ApplicationDetail.application_id)
        .filter(
            Application.user_id == user_id,
            ApplicationDetail.subject_id == subject_id,
            Application.is_active.is_(True),
            ApplicationDetail.is_active.is_(True),
            Application.deleted_at.is_(None),
            ApplicationDetail.deleted_at.is_(None),
        )
        .all()
    )
    for detail, application in details:
        if _status_value(application.status) in CLOSED_APPLICATION_STATUSES:
            continue
        if application_already_logged(db, application.id, subject_id):
            continue
        return application
    return None


def price_for_new_application(db: Session, user_id: int, subject: Subject) -> float:
    """Enrollment uses the subject price. A later application uses extension_price."""
    if not subject_has_study_period(db, user_id, subject.id):
        return float(subject.current_price or 0)
    if subject.extension_price is None:
        raise StudyAccessError("Extension price is not configured for this subject")
    return float(subject.extension_price)


def _extension_rows(db: Session, root_id: int):
    return (
        db.query(Application)
        .filter(
            Application.original_application_id == root_id,
            Application.deleted_at.is_(None),
        )
        .order_by(Application.id.asc())
        .all()
    )


def _counts_toward_limit(application: Application) -> bool:
    return _status_value(application.status) not in CLOSED_APPLICATION_STATUSES


def extension_root_id_for_subject(db: Session, user_id: int, subject_id: int) -> Optional[int]:
    """Root application for a subject the student has already started, if any."""
    period = (
        _periods_query(db, user_id, subject_id)
        .order_by(StudyPeriod.id.asc())
        .first()
    )
    if period is None:
        return None
    application = db.query(Application).filter(Application.id == period.application_id).first()
    if application is None:
        return period.application_id
    return root_application_id(application.id, application.original_application_id)


def assert_extension_allowed(db: Session, root_id: int) -> int:
    """Return how many extensions already count, or reject a fourth."""
    used = sum(1 for row in _extension_rows(db, root_id) if _counts_toward_limit(row))
    if used >= MAX_EXTENSIONS:
        raise StudyAccessError(
            "This application already has the maximum of three extensions",
            400,
            "extension_limit_reached",
        )
    return used


def application_link_summary(db: Session, application: Application) -> dict:
    """The original application and every extension linked to it."""
    root_id = root_application_id(application.id, application.original_application_id)
    rows = _extension_rows(db, root_id)
    used = sum(1 for row in rows if _counts_toward_limit(row))
    return {
        "original_application_id": None if application.id == root_id else root_id,
        "root_application_id": root_id,
        "extension_count": used,
        "extensions_remaining": extensions_remaining(used),
        "extensions": [
            {
                "id": row.id,
                "status": _status_value(row.status),
                "payment_status": _status_value(row.payment_status),
                "total_fee": row.total_fee,
                "created_at": _iso_datetime(row.created_at),
            }
            for row in rows
        ],
    }


def open_periods_for_approved_application(db: Session, application: Application, actor_id: int) -> list:
    """Write a study row when an extension application is approved.

    The first enrollment does not start the clock. A later approved application
    for a subject the student has already started does, and that row stores the
    new application id.
    """
    if _status_value(application.status) != ApplicationStatus.approved.value:
        return []

    details = application.details
    if details is None:
        details = (
            db.query(ApplicationDetail)
            .filter(
                ApplicationDetail.application_id == application.id,
                ApplicationDetail.deleted_at.is_(None),
            )
            .all()
        )

    created = []
    today = _today()
    for detail in details:
        if not detail.is_active or detail.deleted_at is not None:
            continue
        if application_already_logged(db, application.id, detail.subject_id):
            continue
        prior = _periods_query(db, application.user_id, detail.subject_id).all()
        if not prior:
            continue
        subject = db.query(Subject).filter(Subject.id == detail.subject_id).first()
        if subject is None or not subject.duration_days or subject.duration_days <= 0:
            continue
        latest = max(prior, key=lambda period: (period.expected_end_date, period.id or 0))
        start = extension_start_date(latest.expected_end_date, today)
        period = StudyPeriod(
            application_id=application.id,
            user_id=application.user_id,
            subject_id=detail.subject_id,
            period_type=PERIOD_EXTENSION,
            start_date=start,
            allocated_days=subject.duration_days,
            expected_end_date=expected_end_date(start, subject.duration_days),
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(period)
        created.append(period)
    return created


def _approved_application(db: Session, user_id: int, application_id: int, subject_id: int):
    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.user_id == user_id,
            Application.is_active.is_(True),
            Application.deleted_at.is_(None),
        )
        .first()
    )
    if not application:
        raise StudyAccessError("Application not found", 404)
    if _status_value(application.status) != ApplicationStatus.approved.value:
        raise StudyAccessError("Study time starts only after the application is approved", 400)

    detail = (
        db.query(ApplicationDetail)
        .filter(
            ApplicationDetail.application_id == application_id,
            ApplicationDetail.subject_id == subject_id,
            ApplicationDetail.is_active.is_(True),
            ApplicationDetail.deleted_at.is_(None),
        )
        .first()
    )
    if not detail:
        raise StudyAccessError("This application does not include that subject", 400)

    subject = (
        db.query(Subject)
        .filter(
            Subject.id == subject_id,
            Subject.is_active.is_(True),
            Subject.deleted_at.is_(None),
        )
        .first()
    )
    if not subject:
        raise StudyAccessError("Subject not found", 404)
    return application, subject


def _period_payload(period: StudyPeriod, subject: Optional[Subject] = None) -> dict:
    payload = {
        "id": period.id,
        "application_id": period.application_id,
        "user_id": period.user_id,
        "subject_id": period.subject_id,
        "period_type": period.period_type,
        "start_date": _iso_date(period.start_date),
        "allocated_days": period.allocated_days,
        "expected_end_date": _iso_date(period.expected_end_date),
        "is_active": period.is_active,
        "created_at": _iso_datetime(period.created_at),
    }
    if subject is not None:
        payload["subject_name"] = subject.name
        payload["subject_code"] = subject.code
    return payload


class StudyAccessService:
    def __init__(self, db: Session):
        self.db = db

    def start_period(self, user_id: int, application_id: int, subject_id: int) -> tuple:
        _, subject = _approved_application(self.db, user_id, application_id, subject_id)
        if not subject.duration_days or subject.duration_days <= 0:
            raise StudyAccessError("This subject has no study duration configured", 400)

        existing_for_application = (
            _periods_query(self.db, user_id, subject_id)
            .filter(StudyPeriod.application_id == application_id)
            .first()
        )
        if existing_for_application is not None:
            today = _today()
            window = classify_study_window([existing_for_application], today, subject.duration_days)
            if window["can_study"]:
                return _period_payload(existing_for_application, subject), 200
            raise StudyAccessError(
                "Your study period has ended. Submit a new application to continue.",
                400,
                STUDY_PERIOD_ENDED,
            )

        periods = _periods_query(self.db, user_id, subject_id).all()
        if periods:
            raise StudyAccessError(
                "Study already started for this subject. Submit a new application to extend it.",
                400,
                STUDY_PERIOD_ENDED,
            )

        start = _today()
        period = StudyPeriod(
            application_id=application_id,
            user_id=user_id,
            subject_id=subject_id,
            period_type=PERIOD_INITIAL,
            start_date=start,
            allocated_days=subject.duration_days,
            expected_end_date=expected_end_date(start, subject.duration_days),
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(period)
        self.db.commit()
        self.db.refresh(period)
        return _period_payload(period, subject), 201

    def list_my_periods(self, user_id: int, subject_id: Optional[int] = None) -> list:
        query = (
            self.db.query(StudyPeriod, Subject)
            .join(Subject, Subject.id == StudyPeriod.subject_id)
            .filter(
                StudyPeriod.user_id == user_id,
                StudyPeriod.deleted_at.is_(None),
            )
            .order_by(StudyPeriod.start_date.desc(), StudyPeriod.id.desc())
        )
        if subject_id is not None:
            query = query.filter(StudyPeriod.subject_id == subject_id)
        return [_period_payload(period, subject) for period, subject in query.all()]

    def windows_for_user(self, user_id: int, subject_ids: list, on_date: Optional[date] = None) -> dict:
        if not subject_ids:
            return {}
        on_date = on_date or _today()
        subjects = {
            subject.id: subject
            for subject in self.db.query(Subject).filter(Subject.id.in_(subject_ids)).all()
        }
        applications = (
            self.db.query(Application.id, ApplicationDetail.subject_id)
            .join(ApplicationDetail, ApplicationDetail.application_id == Application.id)
            .filter(
                Application.user_id == user_id,
                Application.status == ApplicationStatus.approved,
                Application.is_active.is_(True),
                Application.deleted_at.is_(None),
                ApplicationDetail.subject_id.in_(subject_ids),
                ApplicationDetail.is_active.is_(True),
                ApplicationDetail.deleted_at.is_(None),
            )
            .all()
        )
        application_by_subject = {}
        for application_id, subject_id in applications:
            current = application_by_subject.get(subject_id)
            if current is None or application_id > current:
                application_by_subject[subject_id] = application_id

        periods = (
            self.db.query(StudyPeriod)
            .filter(
                StudyPeriod.user_id == user_id,
                StudyPeriod.subject_id.in_(subject_ids),
                StudyPeriod.deleted_at.is_(None),
                StudyPeriod.is_active.is_(True),
            )
            .all()
        )
        periods_by_subject = {}
        for period in periods:
            periods_by_subject.setdefault(period.subject_id, []).append(period)

        first_application_ids = [
            min(subject_periods, key=lambda item: item.id or 0).application_id
            for subject_periods in periods_by_subject.values()
        ]
        root_by_application = {}
        if first_application_ids:
            for application in self.db.query(Application).filter(Application.id.in_(first_application_ids)).all():
                root_by_application[application.id] = root_application_id(
                    application.id, application.original_application_id
                )
        used_by_root = {}
        root_ids = set(root_by_application.values())
        if root_ids:
            linked = (
                self.db.query(Application)
                .filter(
                    Application.original_application_id.in_(root_ids),
                    Application.deleted_at.is_(None),
                )
                .all()
            )
            for row in linked:
                if _counts_toward_limit(row):
                    used_by_root[row.original_application_id] = used_by_root.get(row.original_application_id, 0) + 1

        windows = {}
        for subject_id in subject_ids:
            subject = subjects.get(subject_id)
            duration_days = subject.duration_days if subject else None
            subject_periods = periods_by_subject.get(subject_id, [])
            classified = classify_study_window(subject_periods, on_date, duration_days)
            period = classified["period"]
            extension_price = None
            if subject is not None and subject.extension_price is not None:
                extension_price = float(subject.extension_price)
            root_id = None
            remaining = None
            if subject_periods:
                first = min(subject_periods, key=lambda item: item.id or 0)
                root_id = root_by_application.get(first.application_id, first.application_id)
                remaining = extensions_remaining(used_by_root.get(root_id, 0))
            windows[subject_id] = {
                "status": classified["status"],
                "can_study": classified["can_study"],
                "access_expired": classified["access_expired"],
                "application_id": period.application_id if period is not None else application_by_subject.get(subject_id),
                "original_application_id": root_id,
                "period_id": period.id if period is not None else None,
                "period_type": period.period_type if period is not None else None,
                "start_date": _iso_date(period.start_date) if period is not None else None,
                "allocated_days": period.allocated_days if period is not None else duration_days,
                "expected_end_date": _iso_date(period.expected_end_date) if period is not None else None,
                "days_remaining": classified["days_remaining"],
                "extension_price": extension_price,
                "extensions_remaining": remaining,
                "can_apply_for_extension": bool(subject_periods) and remaining > 0,
            }
        return windows
