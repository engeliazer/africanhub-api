from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database.base import Base


class PublicNotification(Base):
    __tablename__ = "public_notifications"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False, default="general", server_default="general")
    link = Column(String(1000), nullable=True)
    starts_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_published = Column(Boolean, nullable=False, default=False, server_default="0")
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class PublicNotificationRead(Base):
    __tablename__ = "public_notification_reads"
    __table_args__ = (
        UniqueConstraint("notification_id", "visitor_id", name="uq_public_notification_read_visitor"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    notification_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("public_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visitor_id = Column(String(255), nullable=False, index=True)
    read_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
