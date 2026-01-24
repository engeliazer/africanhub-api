from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from applications.models.models import PaymentStatus, ApplicationStatus, PaymentMethod

# Application Detail Schemas
class ApplicationDetailBase(BaseModel):
    subject_id: int
    fee: Optional[float] = None
    status: str = ApplicationStatus.pending.value
    is_active: bool = True
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    @validator('status')
    def status_must_be_valid(cls, v):
        if v not in [s.value for s in ApplicationStatus]:
            raise ValueError(f'Status must be one of {[s.value for s in ApplicationStatus]}')
        return v

class ApplicationDetailCreate(ApplicationDetailBase):
    pass

class ApplicationDetailUpdate(BaseModel):
    subject_id: Optional[int] = None
    fee: Optional[float] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: Optional[int] = None

    @validator('status')
    def status_must_be_valid(cls, v):
        if v is not None and v not in [s.value for s in ApplicationStatus]:
            raise ValueError(f'Status must be one of {[s.value for s in ApplicationStatus]}')
        return v

class ApplicationDetailInDB(ApplicationDetailBase):
    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    
    class Config:
        from_attributes = True

# Application Schemas
class ApplicationBase(BaseModel):
    user_id: int
    payment_status: str = PaymentStatus.pending_payment.value
    total_fee: Optional[float] = 0.0
    status: str = ApplicationStatus.pending.value
    is_active: bool = True
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    @validator('payment_status')
    def payment_status_must_be_valid(cls, v):
        if v not in [s.value for s in PaymentStatus]:
            raise ValueError(f'Payment status must be one of {[s.value for s in PaymentStatus]}')
        return v

    @validator('status')
    def status_must_be_valid(cls, v):
        if v not in [s.value for s in ApplicationStatus]:
            raise ValueError(f'Status must be one of {[s.value for s in ApplicationStatus]}')
        return v

class ApplicationCreate(ApplicationBase):
    details: List[ApplicationDetailCreate]

class ApplicationUpdate(BaseModel):
    user_id: Optional[int] = None
    payment_status: Optional[str] = None
    total_fee: Optional[float] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    updated_by: Optional[int] = None
    
    @validator('payment_status')
    def payment_status_must_be_valid(cls, v):
        if v is not None and v not in [s.value for s in PaymentStatus]:
            raise ValueError(f'Payment status must be one of {[s.value for s in PaymentStatus]}')
        return v
    
    @validator('status')
    def status_must_be_valid(cls, v):
        if v is not None and v not in [s.value for s in ApplicationStatus]:
            raise ValueError(f'Status must be one of {[s.value for s in ApplicationStatus]}')
        return v

class ApplicationInDB(ApplicationBase):
    id: int
    details: List[ApplicationDetailInDB] = []
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    
    class Config:
        from_attributes = True

# Schema for creating a season application (multiple subjects for one season)
class SeasonApplicationCreate(BaseModel):
    user_id: int
    subject_ids: List[int]
    payment_status: str = PaymentStatus.pending_payment.value
    status: str = ApplicationStatus.pending.value
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    
    @validator('payment_status')
    def payment_status_must_be_valid(cls, v):
        if v not in [s.value for s in PaymentStatus]:
            raise ValueError(f'Payment status must be one of {[s.value for s in PaymentStatus]}')
        return v
    
    @validator('status')
    def status_must_be_valid(cls, v):
        if v not in [s.value for s in ApplicationStatus]:
            raise ValueError(f'Status must be one of {[s.value for s in ApplicationStatus]}')
        return v

# Payment Schemas
class PaymentBase(BaseModel):
    amount: float
    payment_method: str
    mobile_number: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    @validator('payment_method')
    def payment_method_must_be_valid(cls, v):
        """Validate payment method against enum values.
        This is the single source of truth for payment method validation.
        """
        try:
            # First try direct value match
            for method in PaymentMethod:
                if v == method.value:
                    return v
            # If no direct match, try creating from value
            PaymentMethod(v)
            return v
        except ValueError:
            raise ValueError(f'Payment method must be one of {[m.value for m in PaymentMethod]}')

class PaymentDetail(BaseModel):
    """Payment detail schema"""
    id: Optional[int] = None
    payment_id: int
    application_id: int
    amount: float
    is_active: Optional[bool] = True
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    """Payment create schema"""
    transaction_id: str
    amount: float
    payment_method: str
    payment_status: str = 'pending'
    payment_date: datetime = datetime.utcnow()
    mobile_number: Optional[str] = None
    description: Optional[str] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class PaymentUpdate(BaseModel):
    """Payment update schema"""
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_date: Optional[datetime] = None
    mobile_number: Optional[str] = None
    description: Optional[str] = None
    updated_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class PaymentInDB(PaymentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None
    deleted_at: Optional[datetime] = None
    payment_details: Optional[PaymentDetail] = None

    class Config:
        orm_mode = True


class PaymentResponse(BaseModel):
    message: str
    payment: PaymentInDB


class PaymentListResponse(BaseModel):
    message: str
    payments: List[PaymentInDB]
    total: int


# Payment Detail Schemas
class PaymentDetailBase(BaseModel):
    payment_id: int
    application_id: int
    amount: float
    is_active: bool = True
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

class PaymentDetailCreate(PaymentDetailBase):
    pass

class PaymentDetailUpdate(BaseModel):
    amount: Optional[float] = None
    is_active: Optional[bool] = None
    updated_by: Optional[int] = None

class PaymentDetailInDB(PaymentDetailBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    
    class Config:
        from_attributes = True 