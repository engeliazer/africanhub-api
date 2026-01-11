from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime, Integer
from sqlalchemy.sql import func
from database.base import Base

class Testimonial(Base):
    __tablename__ = "testimonials"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)  # Link to users table
    role = Column(String(255), nullable=True)  # e.g., "CPA Graduate, 2024"
    text = Column(Text, nullable=False)  # The testimonial text
    photo = Column(String(500), nullable=True)  # URL to testimonial photo
    rating = Column(Integer, nullable=False, default=5)  # Rating from 1-5 stars
    is_approved = Column(Boolean, nullable=False, default=False)  # Admin approval required
    reviewed_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)  # Admin who reviewed
    reviewed_at = Column(DateTime, nullable=True)  # When it was reviewed
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)