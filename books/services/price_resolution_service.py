from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from books.models.sales_models import BookListing, ListingStatus, UserPaidBookEdition
from books.services.pricing_service import get_active_edition_price
from books.services.lms_edition_helpers import book_reference_id
from services.lms_client import LMSClient, LMSClientError


class PriceResolutionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def user_has_completed_book_purchase(
    db: Session,
    user_id: int,
    book_reference_id: str,
) -> bool:
    return (
        db.query(UserPaidBookEdition.id)
        .filter(
            UserPaidBookEdition.user_id == user_id,
            UserPaidBookEdition.book_reference_id == book_reference_id,
        )
        .first()
        is not None
    )


def resolve_customer_price(
    db: Session,
    lms_client: LMSClient,
    user_id: int,
    edition_reference_id: str,
) -> dict:
    listing = (
        db.query(BookListing)
        .filter(
            BookListing.edition_reference_id == edition_reference_id,
            BookListing.status == ListingStatus.LISTED.value,
        )
        .first()
    )
    if not listing:
        raise PriceResolutionError("Edition is not listed for sale", 404)

    price_row = get_active_edition_price(db, edition_reference_id)
    if not price_row:
        raise PriceResolutionError("No active price for this edition", 409)

    try:
        edition = lms_client.get_edition(edition_reference_id)
    except LMSClientError as exc:
        raise PriceResolutionError("Failed to load edition from LMS", 502) from exc

    parent_book_ref = book_reference_id(edition)
    if not parent_book_ref:
        raise PriceResolutionError("Edition is missing parent book reference from LMS", 502)

    is_previous_buyer = user_has_completed_book_purchase(db, user_id, parent_book_ref)

    if is_previous_buyer:
        customer_type = "PREVIOUS_BUYER"
        amount = price_row.previous_buyer_price
    else:
        customer_type = "NEW_BUYER"
        amount = price_row.new_buyer_price

    return {
        "edition_reference_id": edition_reference_id,
        "customer_type": customer_type,
        "price": float(amount),
        "currency": price_row.currency,
        "book_reference_id": parent_book_ref,
        "unit_price_decimal": Decimal(str(amount)),
    }


def build_store_edition_payload(db: Session, listing: BookListing) -> Optional[dict]:
    price_row = get_active_edition_price(db, listing.edition_reference_id)
    if not price_row:
        return None
    return {
        "edition_reference_id": listing.edition_reference_id,
        "new_buyer_price": float(price_row.new_buyer_price),
        "previous_buyer_price": float(price_row.previous_buyer_price),
        "currency": price_row.currency,
        "status": listing.status,
    }
