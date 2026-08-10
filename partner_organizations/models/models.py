from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Integer
from sqlalchemy.sql import func
from database.base import Base


class PartnerOrganization(Base):
    """Organizations the platform has worked with (trust / social proof)."""
    __tablename__ = "partner_organizations"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    logo = Column(String(500), nullable=True)
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
