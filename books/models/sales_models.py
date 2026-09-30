import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    BigInteger,
    Numeric,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from database.db_connector import Base


class ListingStatus(str, enum.Enum):
    LISTED = "LISTED"
    UNLISTED = "UNLISTED"


class BookOrderStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class EditionPrice(Base):
    __tablename__ = "edition_prices"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    edition_reference_id = Column(String(100), nullable=False, index=True)
    new_buyer_price = Column(Numeric(12, 2), nullable=False)
    previous_buyer_price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="TZS")
    is_active = Column(Boolean, nullable=False, default=True)
    effective_from = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    effective_to = Column(DateTime, nullable=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    creator = relationship("User", foreign_keys=[created_by])


class BookListing(Base):
    __tablename__ = "book_listings"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    edition_reference_id = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default=ListingStatus.UNLISTED.value)
    listed_at = Column(DateTime, nullable=True)
    listed_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    unlisted_at = Column(DateTime, nullable=True)
    unlisted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    lister = relationship("User", foreign_keys=[listed_by])
    unlister = relationship("User", foreign_keys=[unlisted_by])


class BookOrder(Base):
    __tablename__ = "book_orders"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_number = Column(String(50), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default=BookOrderStatus.pending.value)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="TZS")
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    items = relationship("BookOrderItem", back_populates="order", cascade="all, delete-orphan")


class BookOrderItem(Base):
    __tablename__ = "book_order_items"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    order_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("book_orders.id", ondelete="CASCADE"), nullable=False)
    book_reference_id = Column(String(100), nullable=False, index=True)
    edition_reference_id = Column(String(100), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False)
    total_price = Column(Numeric(12, 2), nullable=False)

    order = relationship("BookOrder", back_populates="items")

    __table_args__ = (
        UniqueConstraint("order_id", "edition_reference_id", name="uq_book_order_item_edition"),
    )
