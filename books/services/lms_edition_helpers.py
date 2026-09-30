"""Helpers for normalizing LMS book/edition payloads."""

from typing import Any, Dict, Optional


def edition_reference_id(edition: Dict[str, Any]) -> Optional[str]:
    for key in ("version_reference_id", "edition_reference_id", "reference_id", "id"):
        value = edition.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def book_reference_id(edition: Dict[str, Any]) -> Optional[str]:
    direct = edition.get("book_reference_id") or edition.get("book_reference")
    if direct:
        return str(direct)

    book = edition.get("book")
    if isinstance(book, dict):
        for key in ("reference_id", "book_reference_id", "id"):
            value = book.get(key)
            if value is not None and str(value).strip():
                return str(value)
    return None


def edition_is_published(edition: Dict[str, Any]) -> bool:
    if edition.get("is_published") is True or edition.get("published") is True:
        return True

    status = (
        edition.get("publication_status")
        or edition.get("publish_status")
        or edition.get("status")
        or ""
    )
    normalized = str(status).upper().replace(" ", "_")
    return normalized in {
        "PUBLISHED",
        "ACTIVE",
        "PUBLISH",
        "LIVE",
        "READY",
    }
