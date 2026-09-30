from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from books.models.sales_models import BookListing, ListingStatus
from books.services.pricing_service import get_active_edition_price
from books.services.lms_edition_helpers import edition_is_published
from services.lms_client import LMSClient, LMSClientError


class ListingValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def get_listing(db: Session, edition_reference_id: str) -> Optional[BookListing]:
    return (
        db.query(BookListing)
        .filter(BookListing.edition_reference_id == edition_reference_id)
        .first()
    )


def get_or_create_listing(db: Session, edition_reference_id: str) -> BookListing:
    listing = get_listing(db, edition_reference_id)
    if listing:
        return listing
    listing = BookListing(
        edition_reference_id=edition_reference_id,
        status=ListingStatus.UNLISTED.value,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def validate_edition_for_listing(
    lms_client: LMSClient,
    db: Session,
    edition_reference_id: str,
) -> dict:
    try:
        edition = lms_client.get_edition(edition_reference_id)
    except LMSClientError as exc:
        if exc.status_code == 404:
            raise ListingValidationError("Edition not found in LMS", 404) from exc
        raise ListingValidationError("Failed to validate edition with LMS", 502) from exc

    if not edition_is_published(edition):
        raise ListingValidationError("Edition is not published in LMS", 409)

    if not get_active_edition_price(db, edition_reference_id):
        raise ListingValidationError("No active price configured for this edition", 409)

    listing = get_listing(db, edition_reference_id)
    if listing and listing.status == ListingStatus.LISTED.value:
        raise ListingValidationError("Edition is already listed", 409)

    return edition


def list_edition(
    db: Session,
    lms_client: LMSClient,
    edition_reference_id: str,
    listed_by: int,
) -> BookListing:
    validate_edition_for_listing(lms_client, db, edition_reference_id)
    now = datetime.utcnow()
    listing = get_or_create_listing(db, edition_reference_id)
    listing.status = ListingStatus.LISTED.value
    listing.listed_at = now
    listing.listed_by = listed_by
    listing.unlisted_at = None
    listing.unlisted_by = None
    db.commit()
    db.refresh(listing)
    return listing


def unlist_edition(db: Session, edition_reference_id: str, unlisted_by: int) -> BookListing:
    listing = get_listing(db, edition_reference_id)
    if not listing or listing.status != ListingStatus.LISTED.value:
        raise ListingValidationError("Edition is not currently listed", 404)

    listing.status = ListingStatus.UNLISTED.value
    listing.unlisted_at = datetime.utcnow()
    listing.unlisted_by = unlisted_by
    db.commit()
    db.refresh(listing)
    return listing


def list_listed_editions(db: Session) -> List[BookListing]:
    return (
        db.query(BookListing)
        .filter(BookListing.status == ListingStatus.LISTED.value)
        .order_by(BookListing.listed_at.desc())
        .all()
    )


def listing_to_response(listing: BookListing) -> dict:
    return {
        "edition_reference_id": listing.edition_reference_id,
        "status": listing.status,
        "listed_at": listing.listed_at.isoformat() if listing.listed_at else None,
        "unlisted_at": listing.unlisted_at.isoformat() if listing.unlisted_at else None,
    }
