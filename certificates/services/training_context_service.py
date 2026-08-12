from datetime import date
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from certificates.models.models import CertificateTemplate, CertificateTrainingContext
from subjects.models.models import Course, Subject


def _training_record(
    db: Session,
    training_type: str,
    training_id: int,
) -> Tuple[Optional[Any], Optional[str]]:
    if training_type == "course":
        row = (
            db.query(Course)
            .filter(Course.id == training_id, Course.deleted_at.is_(None))
            .first()
        )
        if not row:
            return None, "Course not found"
        return row, None

    row = (
        db.query(Subject)
        .filter(Subject.id == training_id, Subject.deleted_at.is_(None))
        .first()
    )
    if not row:
        return None, "Subject not found"
    return row, None


def resolve_subject_title(
    db: Session,
    training_type: str,
    training_id: int,
    override: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    if override and override.strip():
        return override.strip(), None

    record, error = _training_record(db, training_type, training_id)
    if error:
        return "", error
    return record.name, None


def get_active_template(db: Session, template_id: int) -> Tuple[Optional[CertificateTemplate], Optional[str]]:
    row = (
        db.query(CertificateTemplate)
        .filter(
            CertificateTemplate.id == template_id,
            CertificateTemplate.deleted_at.is_(None),
            CertificateTemplate.is_active == True,
        )
        .first()
    )
    if not row:
        return None, "Certificate template not found or inactive"
    return row, None


def find_training_context(
    db: Session,
    training_type: str,
    training_id: int,
) -> Optional[CertificateTrainingContext]:
    return (
        db.query(CertificateTrainingContext)
        .filter(
            CertificateTrainingContext.training_type == training_type,
            CertificateTrainingContext.training_id == training_id,
            CertificateTrainingContext.deleted_at.is_(None),
        )
        .first()
    )


def validate_training_context_data(data: Dict[str, Any]) -> Optional[str]:
    host_mode = data.get("host_mode", "single")
    if host_mode == "collaboration":
        if not data.get("invited_organization_name"):
            return "invited_organization_name is required for collaboration mode"
        if not data.get("invited_code"):
            return "invited_code is required for collaboration mode"
    else:
        data["invited_organization_name"] = None
        data["invited_code"] = None

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    if isinstance(start_date, date) and isinstance(end_date, date) and end_date < start_date:
        return "end_date must be on or after start_date"

    return None


def apply_training_context_fields(
    row: CertificateTrainingContext,
    data: Dict[str, Any],
) -> None:
    for field in (
        "certificate_template_id",
        "host_mode",
        "host_organization_name",
        "invited_organization_name",
        "home_logo_url",
        "invited_logo_url",
        "subject_title",
        "venue_text",
        "start_date",
        "end_date",
        "cpd_hours",
        "cert_number_pattern",
        "home_code",
        "invited_code",
        "signatory_override",
        "updated_by",
    ):
        if field in data:
            setattr(row, field, data[field])
