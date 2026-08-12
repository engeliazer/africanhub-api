from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Integer, Text, Date, Time, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.base import Base


class Event(Base):
    """Public-facing training event / invitation for website display and letter downloads."""

    __tablename__ = "events"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    course_title = Column(String(500), nullable=False)
    course_description = Column(Text, nullable=True)
    venue = Column(String(500), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    learning_outcomes = Column(Text, nullable=True)
    course_fee = Column(Numeric(12, 2), nullable=True)
    deposit_amount = Column(Numeric(12, 2), nullable=True)
    reservation_deadline = Column(Date, nullable=True)
    bank_account_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(100), nullable=True)
    bank_name = Column(String(255), nullable=True)
    is_published = Column(Boolean, nullable=False, default=False)
    invitation_template_path = Column(String(500), nullable=True)
    invitation_template_filename = Column(String(255), nullable=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    trainer_assignments = relationship(
        "EventTrainerAssignment",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventTrainerAssignment.display_order",
    )
    participants = relationship(
        "EventParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventParticipant.id.asc()",
    )


class EventTrainerAssignment(Base):
    """Links reusable invitation trainers to a public event."""

    __tablename__ = "event_trainer_assignments"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    event_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trainer_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        index=True,
    )
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    event = relationship("Event", back_populates="trainer_assignments")


class EventLetterRequest(Base):
    """Audit log when a visitor downloads a personalized invitation letter."""

    __tablename__ = "event_letter_requests"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    event_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name = Column(String(255), nullable=False)
    organization = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


class EventParticipant(Base):
    """Attendance roster for a training calendar event — system users or walk-in guests."""

    __tablename__ = "event_participants"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    event_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("events.id", ondelete="CASCADE"),
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
    organization = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
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

    event = relationship("Event", back_populates="participants")
