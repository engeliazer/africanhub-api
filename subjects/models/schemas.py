from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, date
from subjects.models.models import ApplicationStatus

# Subject schemas
class SubjectBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    current_price: Optional[int] = None
    duration_days: Optional[int] = None
    trial_duration_days: Optional[int] = None
    is_active: bool = True
    created_by: int
    updated_by: int

class SubjectCreate(SubjectBase):
    pass

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    current_price: Optional[int] = None
    duration_days: Optional[int] = None
    trial_duration_days: Optional[int] = None
    is_active: Optional[bool] = None
    updated_by: int

class SubjectInDB(SubjectBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Topic schemas
class TopicBase(BaseModel):
    subject_id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True
    created_by: int
    updated_by: int

class TopicCreate(TopicBase):
    pass

class TopicUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int

class TopicInDB(TopicBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# SubTopic schemas
class SubTopicBase(BaseModel):
    topic_id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True
    created_by: int
    updated_by: int

class SubTopicCreate(SubTopicBase):
    pass

class SubTopicUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int

class SubTopicInDB(SubTopicBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Course schemas
class CourseBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True
    created_by: int
    updated_by: int


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int


class CourseInDB(CourseBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Season schemas
class SeasonBase(BaseModel):
    name: str
    code: str
    start_date: date
    end_date: date
    description: Optional[str] = None
    is_active: bool = True
    created_by: int
    updated_by: int


class SeasonCreate(SeasonBase):
    pass


class SeasonUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int


class SeasonInDB(SeasonBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# SeasonSubject schemas
class SeasonSubjectBase(BaseModel):
    season_id: int
    subject_id: int
    is_active: bool = True
    created_by: int
    updated_by: int


class SeasonSubjectCreate(SeasonSubjectBase):
    pass
