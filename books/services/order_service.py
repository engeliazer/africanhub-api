import secrets
from datetime import datetime
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from books.models.sales_models import BookOrder, BookOrderItem, BookOrderStatus
from books.services.price_resolution_service import resolve_customer_price, PriceResolutionError
from services.lms_client import LMSClient


class OrderServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _generate_order_number() -> str:
    return f"BO-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def create_book_order(
    db: Session,
    lms_client: LMSClient,
    user_id: int,
    edition_reference_ids: List[str],
    quantities: List[int],
    mark_completed: bool = False,
) -> BookOrder:
    if len(edition_reference_ids) != len(quantities):
        raise OrderServiceError("Each item must have a quantity")

    order = BookOrder(
        user_id=user_id,
        order_number=_generate_order_number(),
        status=BookOrderStatus.pending.value,
        currency="TZS",
        total_amount=Decimal("0"),
    )
    db.add(order)
    db.flush()

    total = Decimal("0")
    currency = "TZS"

    for edition_ref, qty in zip(edition_reference_ids, quantities):
        try:
            resolved = resolve_customer_price(db, lms_client, user_id, edition_ref)
        except PriceResolutionError as exc:
            raise OrderServiceError(str(exc), exc.status_code) from exc

        unit_price = resolved["unit_price_decimal"]
        line_total = unit_price * qty
        currency = resolved["currency"]

        item = BookOrderItem(
            order_id=order.id,
            book_reference_id=resolved["book_reference_id"],
            edition_reference_id=edition_ref,
            quantity=qty,
            unit_price=unit_price,
            total_price=line_total,
        )
        db.add(item)
        total += line_total

    order.total_amount = total
    order.currency = currency
    if mark_completed:
        order.status = BookOrderStatus.completed.value
        order.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(order)
    return order


def order_to_response(order: BookOrder) -> dict:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "currency": order.currency,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "items": [
            {
                "book_reference_id": item.book_reference_id,
                "edition_reference_id": item.edition_reference_id,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price),
            }
            for item in order.items
        ],
    }
