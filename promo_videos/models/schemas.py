from typing import Optional

from pydantic import BaseModel


class PromoVideoCreate(BaseModel):
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    status: str = "draft"
    video_status: Optional[str] = None
    vdocipher_video_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    sort_order: int = 0


class PromoVideoUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    video_status: Optional[str] = None
    vdocipher_video_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    sort_order: Optional[int] = None
