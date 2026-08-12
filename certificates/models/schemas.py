from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
