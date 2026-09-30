from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from books.models.sales_models import EditionPrice


def get_active_edition_price(
    db: Session,
    edition_reference_id: str,
    at_time: Optional[datetime] = None,
) -> Optional[EditionPrice]:
    moment = at_time or datetime.utcnow()
    return (
        db.query(EditionPrice)
        .filter(
            EditionPrice.edition_reference_id == edition_reference_id,
            EditionPrice.is_active.is_(True),
            EditionPrice.effective_from <= moment,
            (EditionPrice.effective_to.is_(None)) | (EditionPrice.effective_to > moment),
        )
        .order_by(EditionPrice.effective_from.desc())
        .first()
    )


def create_edition_price(
    db: Session,
    edition_reference_id: str,
    new_buyer_price: Decimal,
    previous_buyer_price: Decimal,
    currency: str,
    created_by: int,
) -> EditionPrice:
    now = datetime.utcnow()

    active_prices = (
        db.query(EditionPrice)
        .filter(
            EditionPrice.edition_reference_id == edition_reference_id,
            EditionPrice.is_active.is_(True),
        )
        .all()
    )
    for price in active_prices:
        price.is_active = False
        price.effective_to = now

    price = EditionPrice(
        edition_reference_id=edition_reference_id,
        new_buyer_price=new_buyer_price,
        previous_buyer_price=previous_buyer_price,
        currency=currency,
        is_active=True,
        effective_from=now,
        effective_to=None,
        created_by=created_by,
    )
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


def price_to_response(price: EditionPrice) -> dict:
    return {
        "edition_reference_id": price.edition_reference_id,
        "new_buyer_price": float(price.new_buyer_price),
        "previous_buyer_price": float(price.previous_buyer_price),
        "currency": price.currency,
        "status": "ACTIVE" if price.is_active else "INACTIVE",
        "effective_from": price.effective_from.isoformat() if price.effective_from else None,
        "effective_to": price.effective_to.isoformat() if price.effective_to else None,
    }
