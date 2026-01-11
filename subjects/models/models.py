from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Text, Enum, func, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from database.db_connector import Base
from datetime import datetime
import enum
from auth.models.models import User

class ApplicationStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PAID = "PAID"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"

    def __str__(self):
        return self.value

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

    # Relationships
    subjects = relationship("Subject", back_populates="course", cascade="all, delete-orphan")

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

    # Relationships
    season_subjects = relationship("SeasonSubject", back_populates="season", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    current_price = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    course_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    course = relationship("Course", back_populates="subjects")
    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    season_subjects = relationship("SeasonSubject", back_populates="subject", cascade="all, delete-orphan")

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

    # Relationships
    season = relationship("Season", back_populates="season_subjects")
    subject = relationship("Subject", back_populates="season_subjects")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('season_id', 'subject_id', name='season_subject_unique'),
    )

class SeasonApplicant(Base):
    __tablename__ = "season_applicants"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    season_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default=ApplicationStatus.INITIATED.value)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    user = relationship("User", backref="season_applicants")
    season = relationship("Season", backref="season_applicants")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('user_id', 'season_id', name='user_season_unique'),
    ) 