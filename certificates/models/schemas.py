from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignatoryInput(BaseModel):
    display_order: int = Field(default=1, ge=1)
    full_name: str
    title: str


class SignatoryInDB(SignatoryInput):
    id: int
    signature_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CertificateTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    certificate_title: str = "Certificate of Participation"
    participation_prefix: str = "Participated in the training on"
    venue_template: str = "held at {venue}"
    date_template: str = "from {start_date} to {end_date}"
    cpd_template: str = (
        "from {start_date} to {end_date} and qualified for the award of "
        "{cpd_hours} hours of Continuing Professional Development"
    )
    field_layout: Optional[Dict[str, Any]] = None
    is_active: bool = True


class CertificateTemplateCreate(CertificateTemplateBase):
    background_url: str
    background_filename: Optional[str] = None
    created_by: int
    updated_by: int


class CertificateTemplateInDB(CertificateTemplateBase):
    id: int
    background_url: str
    background_filename: Optional[str] = None
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    signatories: List[SignatoryInDB] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj: Any):
        return cls.model_validate(obj)

    def dict(self, **kwargs):
        return self.model_dump(**kwargs)


def template_payload(template: Any, signatories: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Group 1 response shape for certificate template."""
    rows = signatories if signatories is not None else getattr(template, "signatories", [])
    return {
        "template_id": template.id,
        "name": template.name,
        "description": template.description,
        "background_url": template.background_url,
        "background_filename": template.background_filename,
        "certificate_title": template.certificate_title,
        "participation_prefix": template.participation_prefix,
        "venue_template": template.venue_template,
        "date_template": template.date_template,
        "cpd_template": template.cpd_template,
        "field_layout": template.field_layout,
        "is_active": template.is_active,
        "signatories": [
            {
                "id": row.id,
                "display_order": row.display_order,
                "full_name": row.full_name,
                "title": row.title,
                "signature_url": row.signature_url,
            }
            for row in rows
        ],
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


VALID_TRAINING_TYPES = {"course", "subject", "event"}
VALID_HOST_MODES = {"single", "collaboration"}


class TrainingContextInput(BaseModel):
    training_type: str
    training_id: int
    certificate_template_id: int
    host_mode: str = "single"
    host_organization_name: str
    invited_organization_name: Optional[str] = None
    subject_title: Optional[str] = None
    venue_text: str
    start_date: date
    end_date: date
    cpd_hours: int = 0
    cert_number_pattern: str
    home_code: str
    invited_code: Optional[str] = None
    signatory_override: Optional[List[Dict[str, Any]]] = None

    @field_validator("training_type")
    @classmethod
    def validate_training_type(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in VALID_TRAINING_TYPES:
            raise ValueError("training_type must be 'course', 'subject', or 'event'")
        return normalized

    @field_validator("host_mode")
    @classmethod
    def validate_host_mode(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in VALID_HOST_MODES:
            raise ValueError("host_mode must be 'single' or 'collaboration'")
        return normalized


def training_context_payload(row: Any) -> Dict[str, Any]:
    """Group 2 response shape for certificate training context."""
    is_collaboration = row.host_mode == "collaboration"
    return {
        "id": row.id,
        "training_id": row.training_id,
        "training_type": row.training_type,
        "certificate_template_id": row.certificate_template_id,
        "host_mode": row.host_mode,
        "is_collaboration": is_collaboration,
        "host_organization_name": row.host_organization_name,
        "invited_organization_name": row.invited_organization_name,
        "home_logo_url": row.home_logo_url,
        "invited_logo_url": row.invited_logo_url,
        "subject_title": row.subject_title,
        "venue_text": row.venue_text,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "cpd_hours": row.cpd_hours,
        "cert_number_pattern": row.cert_number_pattern,
        "home_code": row.home_code,
        "invited_code": row.invited_code,
        "signatory_override": row.signatory_override,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class ParticipantInput(BaseModel):
    user_id: int


class ParticipantBulkInput(BaseModel):
    participants: List[ParticipantInput]


class ParticipantUpdateInput(BaseModel):
    qualifies_for_cpd_override: Optional[bool] = None
    confirmation_status: Optional[str] = None

    @field_validator("confirmation_status")
    @classmethod
    def validate_confirmation_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"pending", "confirmed", "excluded"}:
            raise ValueError("confirmation_status must be pending, confirmed, or excluded")
        return normalized


def _format_user_full_name(user: Any, salutation: Any) -> str:
    name_parts = [user.first_name]
    if getattr(user, "middle_name", None):
        name_parts.append(user.middle_name)
    name_parts.append(user.last_name)
    core_name = " ".join(part.strip() for part in name_parts if part and str(part).strip())
    if salutation and salutation.label and str(salutation.label).lower() != "none":
        return f"{salutation.label} {core_name}".strip()
    return core_name


def participant_payload(
    participant: Any,
    user: Any,
    salutation: Any,
    training_context: Any,
) -> Dict[str, Any]:
    """Group 3 response shape for one certificate participant."""
    qualifies_computed = bool(
        salutation
        and salutation.qualifies_for_cpd
        and (training_context.cpd_hours or 0) > 0
    )
    override = participant.qualifies_for_cpd_override
    qualifies_for_cpd = override if override is not None else qualifies_computed
    full_name = _format_user_full_name(user, salutation) if user is not None else None

    return {
        "participant_id": participant.id,
        "user_id": participant.user_id,
        "training_context_id": participant.training_context_id,
        "full_name": full_name,
        "salutation_id": user.salutation_id if user is not None else None,
        "salutation": salutation.label if salutation else None,
        "qualifies_for_cpd_computed": qualifies_computed,
        "qualifies_for_cpd": qualifies_for_cpd,
        "qualifies_for_cpd_override": override,
        "confirmation_status": participant.confirmation_status,
        "certificate_id": participant.certificate_id,
        "created_at": participant.created_at.isoformat() if participant.created_at else None,
        "updated_at": participant.updated_at.isoformat() if participant.updated_at else None,
    }


def salutation_payload(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label,
        "code": row.code,
        "qualifies_for_cpd": row.qualifies_for_cpd,
        "display_order": row.display_order,
        "is_active": row.is_active,
    }


def certificate_output_payload(row: Any) -> Dict[str, Any]:
    """Group 4 response shape for an issued certificate."""
    return {
        "certificate_id": row.id,
        "training_context_id": row.training_context_id,
        "participant_id": row.participant_id,
        "training_id": row.training_id,
        "cert_number": row.cert_number,
        "qualifies_for_cpd": row.qualifies_for_cpd,
        "pdf_url": row.pdf_url,
        "issued_at": row.issued_at.isoformat() if row.issued_at else None,
    }
