from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InstructorBase(BaseModel):
    name: str
    title: Optional[str] = None
    bio: Optional[str] = None
    photo: Optional[str] = None
    is_active: bool = True

class InstructorCreate(InstructorBase):
    created_by: int
    updated_by: int

class InstructorUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    bio: Optional[str] = None
    photo: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int

class InstructorInDB(InstructorBase):
    id: int
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
