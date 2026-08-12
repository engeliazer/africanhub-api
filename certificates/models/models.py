from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


class CertificateTemplate(Base):
    """Visual certificate background + text templates + field layout."""

    __tablename__ = "certificate_templates"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    background_url = Column(String(500), nullable=False)
    background_filename = Column(String(255), nullable=True)
    certificate_title = Column(String(255), nullable=False, default="Certificate of Participation")
    participation_prefix = Column(
        String(500),
        nullable=False,
        default="Participated in the training on",
    )
    venue_template = Column(String(500), nullable=False, default="held at {venue}")
    date_template = Column(String(500), nullable=False, default="from {start_date} to {end_date}")
    cpd_template = Column(
        String(1000),
        nullable=False,
        default=(
            "from {start_date} to {end_date} and qualified for the award of "
            "{cpd_hours} hours of Continuing Professional Development"
        ),
    )
    field_layout = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    deleted_at = Column(DateTime, nullable=True)

    signatories = relationship(
        "CertificateTemplateSignatory",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="CertificateTemplateSignatory.display_order",
    )


class CertificateTemplateSignatory(Base):
    """Default signatory block for a certificate template."""

    __tablename__ = "certificate_template_signatories"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    template_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("certificate_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_order = Column(Integer, nullable=False, default=1)
    full_name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    signature_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    template = relationship("CertificateTemplate", back_populates="signatories")
