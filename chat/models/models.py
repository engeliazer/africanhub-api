from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Float, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_connector import Base

class Chat(Base):
    __tablename__ = 'chats'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    rating_requested_at = Column(DateTime, nullable=True)
    rating_requested_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('users.id'), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="chats")
    rating_requester = relationship("User", foreign_keys=[rating_requested_by])
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")
    rating = relationship("ChatRating", back_populates="chat", uselist=False, cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    chat_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('chats.id'), nullable=False)
    sender_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('users.id'), nullable=False)
    message = Column(Text, nullable=False)
    is_from_user = Column(Boolean, default=True)  # True if message is from user, False if from support
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User")

class ChatRating(Base):
    __tablename__ = 'chat_ratings'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    chat_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    rating = Column(Float, nullable=True)  # Rating from 1 to 5, nullable for requests
    comment = Column(Text, nullable=True)   # Optional comment
    is_request = Column(Boolean, default=False)  # True if this is a rating request
    requested_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('users.id'), nullable=True)  # Who requested the rating
    status = Column(String(20), default='pending')  # pending, rated, declined
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    chat = relationship("Chat", back_populates="rating")
    requester = relationship("User", foreign_keys=[requested_by]) 