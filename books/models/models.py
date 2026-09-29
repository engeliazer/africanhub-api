from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger, Text, func, UniqueConstraint
from sqlalchemy.orm import relationship
from database.db_connector import Base
from datetime import datetime


class BookSubjectLink(Base):
    """Maps an LMS book to a local subject for entitlement checks."""

    __tablename__ = "book_subject_links"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    lms_book_id = Column(Integer, nullable=False, index=True)
    subject_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)

    subject = relationship("Subject")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        UniqueConstraint("lms_book_id", "subject_id", name="uq_book_subject_link"),
    )

    def __repr__(self):
        return f"<BookSubjectLink(id={self.id}, lms_book_id={self.lms_book_id}, subject_id={self.subject_id})>"


class BookAccessGrantLog(Base):
    """Local audit log of LMS access grants issued by this system."""

    __tablename__ = "book_access_grant_logs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lms_book_id = Column(Integer, nullable=False, index=True)
    lms_grant_id = Column(Integer, nullable=True, index=True)
    status = Column(String(50), nullable=False, default="active")
    issued_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<BookAccessGrantLog(id={self.id}, user_id={self.user_id}, lms_book_id={self.lms_book_id})>"
