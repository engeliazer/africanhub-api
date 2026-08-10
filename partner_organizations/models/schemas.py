from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime


class PartnerOrganizationBase(BaseModel):
    name: str
    logo: Optional[str] = None
    website_link: Optional[str] = None
    is_active: bool = True


class PartnerOrganizationCreate(PartnerOrganizationBase):
    created_by: int
    updated_by: int


class PartnerOrganizationUpdate(BaseModel):
    name: Optional[str] = None
    logo: Optional[str] = None
    website_link: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int


class PartnerOrganizationInDB(PartnerOrganizationBase):
    id: int
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj: Any):
        return cls.model_validate(obj)

    def dict(self, **kwargs):
        return self.model_dump(**kwargs)


class PartnerOrganizationPublic(BaseModel):
    id: int
    name: str
    logo: Optional[str] = None
    website_link: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
