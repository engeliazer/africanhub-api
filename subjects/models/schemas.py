from pydantic import BaseModel, validator, ConfigDict
from typing import Optional, List, Any
from datetime import datetime, date
from subjects.models.models import ApplicationStatus


def subject_badge_fields(subject: Any) -> dict:
    """Badge booleans and active flag keys for catalog UI."""
    is_most_popular = bool(getattr(subject, "is_most_popular", False))
    is_best_price = bool(getattr(subject, "is_best_price", False))
    is_most_recent = bool(getattr(subject, "is_most_recent", False))
    flags: List[str] = []
    if is_most_popular:
        flags.append("most_popular")
    if is_best_price:
        flags.append("best_price")
    if is_most_recent:
        flags.append("most_recent")
    return {
        "is_most_popular": is_most_popular,
        "is_best_price": is_best_price,
        "is_most_recent": is_most_recent,
        "flags": flags,
    }


def subject_to_dict(subject: Any, **extra) -> dict:
    """Serialize a Subject ORM row including badge flags."""
    payload = SubjectInDB.model_validate(subject).model_dump()
    payload.update(subject_badge_fields(subject))
    payload.update(extra)
    return payload

# Subject schemas
class SubjectBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    current_price: Optional[int] = None
    duration_days: Optional[int] = None
    trial_duration_days: Optional[int] = None
    display_rank: Optional[int] = None
    is_most_popular: bool = False
    is_best_price: bool = False
    is_most_recent: bool = False
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
    display_rank: Optional[int] = None
    is_most_popular: Optional[bool] = None
    is_best_price: Optional[bool] = None
    is_most_recent: Optional[bool] = None
    is_active: Optional[bool] = None
    updated_by: int

class SubjectInDB(SubjectBase):
    id: int
    details_document_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    # Backward-compatible helpers for existing callers
    @classmethod
    def from_orm(cls, obj: Any):
        return cls.model_validate(obj)

    def dict(self, **kwargs):
        return self.model_dump(**kwargs)

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
