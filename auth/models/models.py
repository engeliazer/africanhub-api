from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func, BigInteger, UniqueConstraint, Text, JSON
from sqlalchemy.orm import relationship
from database.db_connector import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    first_name = Column(String(255), nullable=False)
    middle_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=False)
    phone = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(255), nullable=False, default='ACTIVE')
    password = Column(String(255), nullable=False)
    reset_password = Column(Boolean, nullable=False, default=False, server_default='0')
    registration_mode = Column(String(255), nullable=False)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    remember_token = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)

    # Relationship with UserRole
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", foreign_keys="Chat.user_id", back_populates="user", cascade="all, delete-orphan")
    rating_requests = relationship("Chat", foreign_keys="Chat.rating_requested_by", back_populates="rating_requester")

class Role(Base):
    __tablename__ = "roles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationship with UserRole
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")

class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    # Unique constraint for user_id and role_id
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='user_roles_user_id_role_id_unique'),
    )

class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    visitor_id = Column(String(255), nullable=False, unique=True)
    browser_name = Column(String(255), nullable=False)
    browser_version = Column(String(255), nullable=False)
    os_name = Column(String(255), nullable=False)
    os_version = Column(String(255), nullable=False)
    hardware_info = Column(JSON, nullable=True)  # Store as JSON for better querying
    security_fingerprints = Column(JSON, nullable=True)  # Store as JSON for better querying
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_used = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", backref="devices")

    def __repr__(self):
        return f"<UserDevice(id={self.id}, user_id={self.user_id}, visitor_id={self.visitor_id})>" 