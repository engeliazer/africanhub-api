from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TestimonialBase(BaseModel):
    user_id: int
    role: Optional[str] = None
    text: str
    photo: Optional[str] = None
    rating: int = 5  # Rating from 1-5 stars
    is_active: bool = True

class TestimonialCreate(TestimonialBase):
    created_by: int
    updated_by: int

class TestimonialUpdate(BaseModel):
    role: Optional[str] = None
    text: Optional[str] = None
    photo: Optional[str] = None
    rating: Optional[int] = None
    is_active: Optional[bool] = None
    updated_by: int

class TestimonialReview(BaseModel):
    is_approved: bool
    reviewed_by: int
    updated_by: int

class TestimonialInDB(TestimonialBase):
    id: int
    is_approved: bool
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TestimonialPublic(BaseModel):
    id: int
    name: str  # Will be populated from user table
    role: Optional[str] = None
    text: str
    photo: Optional[str] = None
    rating: int

    class Config:
        from_attributes = True
