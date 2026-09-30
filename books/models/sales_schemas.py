from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal

from pydantic import BaseModel, Field


class EditionPriceCreate(BaseModel):
    new_buyer_price: Decimal = Field(..., ge=0)
    previous_buyer_price: Decimal = Field(..., ge=0)
    currency: str = Field(default="TZS", min_length=3, max_length=10)


class EditionPriceResponse(BaseModel):
    edition_reference_id: str
    new_buyer_price: Decimal
    previous_buyer_price: Decimal
    currency: str
    status: str = "ACTIVE"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class ListingResponse(BaseModel):
    edition_reference_id: str
    status: str
    listed_at: Optional[datetime] = None
    unlisted_at: Optional[datetime] = None


class ListingStatusUpdate(BaseModel):
    status: Literal["LISTED", "UNLISTED"]


class StoreEditionItem(BaseModel):
    edition_reference_id: str
    new_buyer_price: Decimal
    previous_buyer_price: Decimal
    currency: str
    status: str = "LISTED"


class CustomerPriceResponse(BaseModel):
    edition_reference_id: str
    customer_type: str
    price: Decimal
    currency: str


class BookOrderItemCreate(BaseModel):
    edition_reference_id: str
    quantity: int = Field(default=1, ge=1)


class BookOrderCreate(BaseModel):
    items: List[BookOrderItemCreate] = Field(..., min_length=1)


class BookOrderItemResponse(BaseModel):
    book_reference_id: str
    edition_reference_id: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


class BookOrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    total_amount: Decimal
    currency: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    items: List[BookOrderItemResponse]
