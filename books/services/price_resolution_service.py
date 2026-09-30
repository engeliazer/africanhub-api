from decimal import Decimal
from typing import Any, Dict, Optional, Set, Tuple

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


def load_user_paid_purchase_sets(
    db: Session,
    user_id: int,
) -> Tuple[Set[str], Set[str]]:
    """Return (owned_edition_reference_ids, owned_book_reference_ids) for approved purchases."""
    rows = (
        db.query(
            UserPaidBookEdition.edition_reference_id,
            UserPaidBookEdition.book_reference_id,
        )
        .filter(UserPaidBookEdition.user_id == user_id)
        .all()
    )
    editions: Set[str] = set()
    books: Set[str] = set()
    for edition_ref, book_ref in rows:
        if edition_ref:
            editions.add(str(edition_ref))
        if book_ref:
            books.add(str(book_ref))
    return editions, books


def attach_store_user_pricing(
    store_payload: Dict[str, Any],
    user_id: Optional[int],
    owned_editions: Optional[Set[str]] = None,
    owned_books: Optional[Set[str]] = None,
    edition_lms: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    When the caller is authenticated, add purchase flags and the price this user would pay.

    Ownership (edition-level, approved payment only):
    - user_owns_edition / already_purchased: true if this exact edition is in the library
    - can_purchase: false when user_owns_edition
    - store_presentation: OWNED | BUY | BUY_RETURNING | GUEST

    Pricing when not owned:
    - is_previous_buyer: another edition of the same book is owned
    - customer_type: NEW_BUYER | PREVIOUS_BUYER
    - your_price: applicable checkout price
    """
    out = dict(store_payload)
    if user_id is None:
        out["pricing_for_user"] = False
        out["user_owns_edition"] = None
        out["already_purchased"] = None
        out["can_purchase"] = None
        out["store_presentation"] = "GUEST"
        out["is_previous_buyer"] = None
        out["customer_type"] = None
        out["your_price"] = None
        return out

    edition_ref = str(out.get("edition_reference_id") or "")
    parent_ref = out.get("book_reference_id")
    if not parent_ref and edition_lms:
        parent_ref = book_reference_id(edition_lms)
    parent_ref = str(parent_ref) if parent_ref else None

    owned_editions = owned_editions or set()
    owned_books = owned_books or set()

    owns_edition = edition_ref in owned_editions if edition_ref else False
    previous = bool(parent_ref and parent_ref in owned_books and not owns_edition)

    out["pricing_for_user"] = True
    out["user_owns_edition"] = owns_edition
    out["already_purchased"] = owns_edition
    out["can_purchase"] = not owns_edition
    out["is_previous_buyer"] = previous

    if owns_edition:
        out["store_presentation"] = "OWNED"
        out["customer_type"] = None
        out["your_price"] = None
        return out

    if previous:
        out["store_presentation"] = "BUY_RETURNING"
        out["customer_type"] = "PREVIOUS_BUYER"
        out["your_price"] = out.get("previous_buyer_price")
    else:
        out["store_presentation"] = "BUY"
        out["customer_type"] = "NEW_BUYER"
        out["your_price"] = out.get("new_buyer_price")

    return out


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
