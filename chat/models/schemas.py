from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class ChatMessageBase(BaseModel):
    message: str
    is_from_user: bool = True

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessageUpdate(BaseModel):
    is_read: Optional[bool] = None

class ChatMessageInDB(ChatMessageBase):
    id: int
    chat_id: int
    sender_id: int
    created_at: datetime
    is_read: bool
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatBase(BaseModel):
    user_id: int
    is_active: bool = True

class ChatCreate(ChatBase):
    pass

class ChatUpdate(BaseModel):
    is_active: Optional[bool] = None

class ChatRatingBase(BaseModel):
    rating: Optional[float] = Field(None, ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = None
    is_request: Optional[bool] = False
    requested_by: Optional[int] = None
    status: Optional[str] = 'pending'

class ChatRatingCreate(ChatRatingBase):
    pass

class ChatRatingInDB(ChatRatingBase):
    id: int
    chat_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatInDB(BaseModel):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    rating_requested_at: Optional[datetime] = None
    rating_requested_by: Optional[int] = None
    messages: List[ChatMessageInDB] = []
    rating: Optional[ChatRatingInDB] = None

    class Config:
        from_attributes = True 