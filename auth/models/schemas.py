from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Role schemas
class RoleBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True
    created_by: int
    updated_by: int

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: int

class RoleInDB(RoleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# User schemas
class UserBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    phone: str
    email: EmailStr
    status: str = 'ACTIVE'
    registration_mode: str
    created_by: int
    updated_by: int

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None
    reset_password: Optional[bool] = None
    registration_mode: Optional[str] = None
    updated_by: int

class UserInDB(UserBase):
    id: int
    reset_password: bool = False
    email_verified_at: Optional[datetime] = None
    remember_token: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserResponse(UserInDB):
    roles: List[RoleInDB] = []
    default_role: Optional[str] = None

# UserRole schemas
class UserRoleBase(BaseModel):
    user_id: int
    role_id: int
    is_default: bool = False
    is_active: bool = True
    created_by: int
    updated_by: int

class UserRoleCreate(UserRoleBase):
    pass

class UserRoleUpdate(BaseModel):
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    updated_by: int

class UserRoleInDB(UserRoleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserRoleResponse(BaseModel):
    id: int
    user_id: int
    role_id: int
    is_default: bool
    name: str
    code: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserDeviceBase(BaseModel):
    user_id: int
    visitor_id: str
    browser_name: str
    browser_version: str
    os_name: str
    os_version: str
    hardware_info: Optional[str] = None
    security_fingerprints: Optional[str] = None
    is_primary: bool = False
    is_active: bool = True
    created_by: int
    updated_by: int

class UserDeviceCreate(UserDeviceBase):
    pass

class UserDeviceUpdate(BaseModel):
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    updated_by: int

class UserDeviceInDB(UserDeviceBase):
    id: int
    last_used: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True 