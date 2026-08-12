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


VALID_TRAINING_TYPES = {"course", "subject"}
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
            raise ValueError("training_type must be 'course' or 'subject'")
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
