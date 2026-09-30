"""Helpers for normalizing LMS book/edition payloads."""

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.lms_client import LMSClient


def edition_reference_id(edition: Dict[str, Any]) -> Optional[str]:
    for key in ("version_reference_id", "edition_reference_id", "reference_id", "id"):
        value = edition.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _is_uuid_reference(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return len(text) >= 32 and "-" in text


def book_reference_id(edition: Dict[str, Any]) -> Optional[str]:
    direct = edition.get("book_reference_id") or edition.get("book_reference")
    if direct and _is_uuid_reference(direct):
        return str(direct).strip()

    book = edition.get("book")
    if isinstance(book, dict):
        for key in ("reference_id", "book_reference_id"):
            value = book.get(key)
            if value is not None and _is_uuid_reference(value):
                return str(value).strip()
        value = book.get("id")
        if _is_uuid_reference(value):
            return str(value).strip()
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


def _absolute_media_url(client: Optional["LMSClient"], url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if client:
        return client.absolute_url(url)
    return url


def cover_url_from_lms(
    edition: Dict[str, Any],
    client: Optional["LMSClient"] = None,
) -> Optional[str]:
    book = edition.get("book") if isinstance(edition.get("book"), dict) else {}
    for source in (edition, book):
        if not isinstance(source, dict):
            continue
        for key in ("cover_url", "cover_image_url", "cover_image", "cover"):
            raw = source.get(key)
            if raw:
                return _absolute_media_url(client, raw if isinstance(raw, str) else str(raw))
    return None


def display_title_from_lms(edition: Dict[str, Any]) -> Optional[str]:
    book = edition.get("book") if isinstance(edition.get("book"), dict) else {}
    for source in (edition, book):
        if not isinstance(source, dict):
            continue
        for key in ("title", "name", "book_title"):
            value = source.get(key)
            if value:
                return str(value)
    return None


def attach_store_catalog_metadata(
    store_payload: Dict[str, Any],
    edition: Optional[Dict[str, Any]],
    client: Optional["LMSClient"] = None,
) -> Dict[str, Any]:
    """Merge LMS book/edition metadata into a store listing row."""
    out = dict(store_payload)
    if not edition:
        out["edition"] = None
        out["book"] = None
        out["book_reference_id"] = None
        out["title"] = None
        out["author"] = None
        out["cover_url"] = None
        out["edition_label"] = None
        return out

    book = edition.get("book") if isinstance(edition.get("book"), dict) else None
    out["edition"] = edition
    out["book"] = book
    out["book_reference_id"] = book_reference_id(edition)
    out["title"] = display_title_from_lms(edition)
    edition_ref = store_payload.get("edition_reference_id") or edition_reference_id(edition)
    if edition_ref:
        from config import hub_edition_cover_url

        out["cover_url"] = hub_edition_cover_url(str(edition_ref))
    else:
        out["cover_url"] = cover_url_from_lms(edition, client)
    out["author"] = (book or {}).get("author") or edition.get("author")
    out["edition_label"] = (
        edition.get("label")
        or edition.get("version_label")
        or edition.get("edition_name")
        or edition.get("name")
    )
    if book and book.get("description") and "description" not in out:
        out["description"] = book.get("description")
    return out
