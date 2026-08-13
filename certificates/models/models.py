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
    Date,
    Numeric,
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
    watermark_logo_url = Column(String(500), nullable=True)
    watermark_opacity = Column(Numeric(3, 2), nullable=False, default=0.12)
    watermark_style = Column(
        String(20),
        nullable=False,
        default="distributed",
        comment="distributed (tiled) or center",
    )
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


class CertificateTrainingContext(Base):
    """Certificate run configuration for a course, subject, or event (Group 2)."""

    __tablename__ = "certificate_training_contexts"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    training_type = Column(String(20), nullable=False, comment="course, subject, or event")
    training_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        comment="courses.id, subjects.id, or events.id",
    )
    certificate_template_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("certificate_templates.id"),
        nullable=False,
        index=True,
    )
    host_mode = Column(String(20), nullable=False, default="single", comment="single or collaboration")
    host_organization_name = Column(String(255), nullable=False)
    invited_organization_name = Column(String(255), nullable=True)
    home_logo_url = Column(String(500), nullable=True)
    invited_logo_url = Column(String(500), nullable=True)
    subject_title = Column(String(500), nullable=False)
    venue_text = Column(String(500), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    cpd_hours = Column(Integer, nullable=False, default=0)
    cert_number_pattern = Column(String(255), nullable=False)
    home_code = Column(String(50), nullable=False)
    invited_code = Column(String(50), nullable=True)
    signatory_override = Column(JSON, nullable=True)
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

    template = relationship("CertificateTemplate")


class Salutation(Base):
    """Lookup table for participant salutations / titles."""

    __tablename__ = "salutations"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    label = Column(String(100), nullable=False, unique=True, comment="Display label e.g. CPA. Dr.")
    code = Column(String(50), nullable=False, unique=True, comment="Stable code e.g. cpa_dr")
    qualifies_for_cpd = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class CertificateParticipant(Base):
    """Participant roster entry for a certificate training context (Group 3)."""

    __tablename__ = "certificate_participants"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    training_context_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("certificate_training_contexts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=True,
        index=True,
        comment="users.id when linked; NULL for walk-in guests",
    )
    full_name = Column(
        String(255),
        nullable=True,
        comment="Guest name without salutation prefix",
    )
    salutation_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=True,
        index=True,
        comment="Salutation for walk-in guests",
    )
    event_participant_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=True,
        index=True,
        comment="Optional link to event_participants.id for training calendar imports",
    )
    email = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    qualifies_for_cpd_override = Column(Boolean, nullable=True)
    confirmation_status = Column(String(20), nullable=False, default="confirmed")
    serial_no = Column(
        String(255),
        nullable=True,
        unique=True,
        comment="Unique serial: home/invited/training_code/random_suffix",
    )
    certificate_id = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
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

    training_context = relationship("CertificateTrainingContext", backref="participants")


class Certificate(Base):
    """Issued certificate output (Group 4)."""

    __tablename__ = "certificates"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    training_context_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("certificate_training_contexts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("certificate_participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    training_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        comment="Denormalized courses.id, subjects.id, or events.id",
    )
    cert_number = Column(String(255), nullable=False, unique=True)
    qualifies_for_cpd = Column(Boolean, nullable=False, default=False)
    pdf_url = Column(String(500), nullable=False)
    issued_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
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

    training_context = relationship("CertificateTrainingContext")
    participant = relationship("CertificateParticipant")
