"""Store catalog responses (guest and authenticated)."""

from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from books.services.listing_service import get_listing, list_listed_editions
from books.services.lms_edition_helpers import attach_store_catalog_metadata, book_reference_id
from books.services.price_resolution_service import (
    attach_store_user_pricing,
    build_store_edition_payload,
    load_user_paid_purchase_sets,
)
from books.services.store_visibility_service import (
    filter_store_rows_for_visibility,
    is_edition_visible_in_store,
    listed_edition_refs_for_book,
    pick_current_edition_reference,
)
from books.models.sales_models import ListingStatus
from services.lms_client import LMSClient, LMSClientError, get_lms_client


def _load_edition_index(client: Optional[LMSClient]) -> Dict[str, Dict[str, Any]]:
    if not client:
        return {}
    try:
        return client.build_edition_index(published_only=False)
    except LMSClientError:
        return {}


def build_store_books_list(db: Session, user_id: Optional[int]) -> Dict[str, Any]:
    owned_editions: Set[str] = set()
    owned_books: Set[str] = set()
    owned_by_book: dict = {}
    if user_id is not None:
        owned_editions, owned_books, owned_by_book = load_user_paid_purchase_sets(db, user_id)

    client = get_lms_client()
    edition_index = _load_edition_index(client)

    data: List[Dict[str, Any]] = []
    for listing in list_listed_editions(db):
        payload = build_store_edition_payload(db, listing)
        if payload:
            edition = edition_index.get(listing.edition_reference_id)
            row = attach_store_catalog_metadata(payload, edition, client)
            row = attach_store_user_pricing(
                row,
                user_id,
                owned_editions=owned_editions,
                owned_books=owned_books,
                edition_lms=edition,
            )
            data.append(row)

    data = filter_store_rows_for_visibility(
        data,
        edition_index,
        owned_editions,
        owned_by_book,
    )

    body: Dict[str, Any] = {"status": "success", "data": data}
    body["meta"] = {
        "authenticated": user_id is not None,
        "store_edition_policy": (
            "OWNED_AND_CURRENT_FOR_RETURNING_BUYERS"
            if user_id is not None and owned_books
            else "CURRENT_EDITION_ONLY"
        ),
    }
    if user_id is not None:
        body["meta"]["user_owned_edition_ids"] = sorted(owned_editions)
    return body


def build_store_book_detail(
    db: Session,
    edition_reference_id: str,
    user_id: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Dict[str, Any], int]]]:
    """
    Return (success_body, None) or (None, (error_json, status_code)).
    """
    listing = get_listing(db, edition_reference_id)
    if not listing or listing.status != ListingStatus.LISTED.value:
        return None, (
            {"status": "error", "message": "Edition is not listed for sale"},
            404,
        )

    payload = build_store_edition_payload(db, listing)
    if not payload:
        return None, (
            {"status": "error", "message": "No active price for this edition"},
            409,
        )

    owned_editions: Set[str] = set()
    owned_by_book: dict = {}
    if user_id is not None:
        owned_editions, _, owned_by_book = load_user_paid_purchase_sets(db, user_id)

    client = get_lms_client()
    edition_index = _load_edition_index(client)
    edition = edition_index.get(edition_reference_id)
    if edition is None and client:
        try:
            edition = client.get_edition(edition_reference_id)
        except LMSClientError:
            edition = None

    book_ref = book_reference_id(edition) if edition else None
    current_ref = None

    if book_ref:
        all_listed_refs = [lst.edition_reference_id for lst in list_listed_editions(db)]
        listed_for_book = listed_edition_refs_for_book(book_ref, all_listed_refs, edition_index)
        if not is_edition_visible_in_store(
            edition_reference_id,
            book_ref,
            listed_for_book,
            edition_index,
            owned_by_book,
        ):
            return None, (
                {
                    "status": "error",
                    "message": (
                        "This edition is not shown in the store for your account. "
                        "Open the current or your owned edition from the catalog."
                    ),
                },
                404,
            )
        current_ref = pick_current_edition_reference(listed_for_book, edition_index)

    row = attach_store_catalog_metadata(payload, edition, client)
    row = attach_store_user_pricing(
        row,
        user_id,
        owned_editions=owned_editions,
        owned_books=set(owned_by_book.keys()),
        edition_lms=edition,
    )
    ref = str(edition_reference_id)
    owns = ref in owned_editions
    is_current = bool(current_ref and ref == current_ref)
    row["is_current_edition"] = is_current if book_ref else None
    if book_ref:
        row["edition_display_role"] = (
            "OWNED_CURRENT" if owns and is_current else ("OWNED" if owns else "CURRENT")
        )
    else:
        row["edition_display_role"] = "CURRENT"
    row["show_in_store"] = True
    return {"status": "success", "data": row}, None
