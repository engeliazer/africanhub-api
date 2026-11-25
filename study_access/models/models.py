from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from database.db_connector import Base


class StudyPeriod(Base):
    """One logged window of study time for a single application and subject.

    The first row is written when the student starts studying. Each approved
    extension application writes another row, using that new application id.
    """

    __tablename__ = "study_periods"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    application_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_type = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    allocated_days = Column(Integer, nullable=False)
    expected_end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)

    application = relationship("Application", foreign_keys=[application_id])
    user = relationship("User", foreign_keys=[user_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
