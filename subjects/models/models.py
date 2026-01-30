from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Text, Enum, func, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from database.db_connector import Base
from datetime import datetime
import enum
from auth.models.models import User


class Course(Base):
    __tablename__ = "courses"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)

    course_subject_links = relationship("CourseSubject", back_populates="course", foreign_keys="CourseSubject.course_id")


class Season(Base):
    __tablename__ = "seasons"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    season_subjects = relationship("SeasonSubject", back_populates="season")


class CourseSubject(Base):
    """Many-to-many: courses <-> subjects (no course_id on subjects)."""
    __tablename__ = "course_subjects"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    course_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    course = relationship("Course", back_populates="course_subject_links")
    subject = relationship("Subject", back_populates="course_subject_links")


class SeasonSubject(Base):
    __tablename__ = "season_subjects"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    season_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    season = relationship("Season", back_populates="season_subjects")
    subject = relationship("Subject", backref="season_subjects")


class ApplicationStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PAID = "PAID"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"

    def __str__(self):
        return self.value

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    current_price = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    duration_days = Column(Integer, nullable=True, comment="Standard access duration in days")
    trial_duration_days = Column(Integer, nullable=True, comment="Trial period duration in days")
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)

    # Relationships (no course_id - use course_subjects mapping)
    course_subject_links = relationship("CourseSubject", back_populates="subject", foreign_keys="CourseSubject.subject_id")
    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")

class Topic(Base):
    __tablename__ = "topics"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    subject_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    subject = relationship("Subject", back_populates="topics")
    sub_topics = relationship("SubTopic", back_populates="topic", cascade="all, delete-orphan")

class SubTopic(Base):
    __tablename__ = "sub_topics"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    topic_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    topic = relationship("Topic", back_populates="sub_topics")
