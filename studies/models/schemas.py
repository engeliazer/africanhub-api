from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StudyMaterialCategoryBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_protected: Optional[bool] = False

class StudyMaterialCategoryCreate(StudyMaterialCategoryBase):
    created_by: int
    updated_by: int

class StudyMaterialCategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_protected: Optional[bool] = None
    updated_by: int

class StudyMaterialCategoryInDB(StudyMaterialCategoryBase):
    id: int
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SubtopicMaterialBase(BaseModel):
    subtopic_id: int
    material_category_id: int
    name: str
    material_path: str
    extension_type: str
    video_duration: Optional[float] = None
    file_size: Optional[int] = None
    # VdoCipher fields
    vdocipher_video_id: Optional[str] = None
    video_status: Optional[str] = None
    video_thumbnail_url: Optional[str] = None
    video_poster_url: Optional[str] = None
    requires_drm: Optional[bool] = False

class SubtopicMaterialCreate(SubtopicMaterialBase):
    created_by: int
    updated_by: int

class SubtopicMaterialUpdate(BaseModel):
    subtopic_id: Optional[int] = None
    material_category_id: Optional[int] = None
    name: Optional[str] = None
    material_path: Optional[str] = None
    extension_type: Optional[str] = None
    video_duration: Optional[float] = None
    file_size: Optional[int] = None
    # VdoCipher fields
    vdocipher_video_id: Optional[str] = None
    video_status: Optional[str] = None
    video_thumbnail_url: Optional[str] = None
    video_poster_url: Optional[str] = None
    requires_drm: Optional[bool] = None
    updated_by: int

class SubtopicMaterialInDB(SubtopicMaterialBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: int
    updated_by: int

    class Config:
        orm_mode = True 