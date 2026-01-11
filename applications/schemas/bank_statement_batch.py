from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class BankTransactionCreate(BaseModel):
    """Schema for creating a bank transaction"""
    transaction_id: str
    payment_date: datetime
    reference_number: str
    account_number: str
    amount: float

class BankTransactionResponse(BaseModel):
    """Schema for bank transaction response"""
    id: int
    transaction_id: str
    payment_date: datetime
    reference_number: str
    account_number: str
    amount: float
    batch_id: int
    account_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BankStatementBatchCreate(BaseModel):
    """Schema for creating a bank statement batch"""
    account_id: int
    batch_reference: str
    start_date: datetime
    end_date: datetime
    number_of_transactions: int
    total_batch_amount: float
    transactions: List[BankTransactionCreate]

class BankStatementBatchResponse(BaseModel):
    """Schema for bank statement batch response"""
    id: int
    account_id: int
    batch_reference: str
    start_date: datetime
    end_date: datetime
    number_of_transactions: int
    total_batch_amount: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    transactions: List[BankTransactionResponse]

    class Config:
        from_attributes = True

class BankStatementBatchUpdate(BaseModel):
    """Schema for updating a bank statement batch"""
    batch_reference: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    number_of_transactions: Optional[int] = None
    total_batch_amount: Optional[float] = None
    is_active: Optional[bool] = None 