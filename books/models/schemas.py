from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class BookSubjectLinkCreate(BaseModel):
    lms_book_id: int
    subject_id: int
    title: Optional[str] = None
    description: Optional[str] = None


class BookSubjectLinkUpdate(BaseModel):
    subject_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class BookSubjectLinkInDB(BaseModel):
    id: int
    lms_book_id: int
    subject_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookAccessRequest(BaseModel):
    ttl_seconds: Optional[int] = Field(default=None, ge=300, le=7200)


class BookCatalogItem(BaseModel):
    id: int
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    is_linked: bool = False


class BookAccessGrantLogInDB(BaseModel):
    id: int
    user_id: int
    lms_book_id: int
    lms_grant_id: Optional[int] = None
    status: str
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
