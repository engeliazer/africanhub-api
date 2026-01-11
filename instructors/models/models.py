from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime, Integer
from sqlalchemy.sql import func
from database.base import Base

class Instructor(Base):
    __tablename__ = "instructors"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)  # e.g., "CPA, PhD in Accounting"
    bio = Column(Text, nullable=True)
    photo = Column(String(500), nullable=True)  # URL to instructor photo
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)
