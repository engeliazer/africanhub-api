"""
Which listed editions to show in the store per book (current vs owned).
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from books.services.lms_edition_helpers import edition_reference_id


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def edition_recency_key(edition: Dict[str, Any]) -> Tuple[int, float, float, str]:
    """Sort key: higher = more likely the 'current' edition."""
    priority = 0
    for flag in ("is_current", "is_latest", "is_primary", "is_default"):
        if edition.get(flag) is True:
            priority = 1
            break

    version_raw = (
        edition.get("version_number")
        or edition.get("edition_number")
        or edition.get("version")
        or edition.get("sequence")
    )
    version_score = 0.0
    if isinstance(version_raw, (int, float)):
        version_score = float(version_raw)
    elif isinstance(version_raw, str):
        digits = "".join(c for c in version_raw if c.isdigit() or c == ".")
        try:
            version_score = float(digits) if digits else 0.0
        except ValueError:
            version_score = 0.0

    ts = 0.0
    for date_key in ("published_at", "release_date", "effective_from", "created_at", "updated_at"):
        dt = _parse_datetime(edition.get(date_key))
        if dt:
            ts = dt.timestamp()
            break

    ref = edition_reference_id(edition) or ""
    return (priority, version_score, ts, ref)


def listed_edition_refs_for_book(
    book_reference_id: str,
    all_listed_edition_refs: List[str],
    edition_index: Dict[str, Dict[str, Any]],
) -> List[str]:
    from books.services.lms_edition_helpers import book_reference_id as lms_book_ref

    book_key = str(book_reference_id)
    refs: List[str] = []
    for ref in all_listed_edition_refs:
        edition = edition_index.get(ref)
        if edition and lms_book_ref(edition) == book_key:
            refs.append(ref)
    return refs


def pick_current_edition_reference(
    listed_edition_refs: List[str],
    edition_index: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    candidates = [
        edition_index[ref]
        for ref in listed_edition_refs
        if ref in edition_index and isinstance(edition_index[ref], dict)
    ]
    if candidates:
        best = max(candidates, key=edition_recency_key)
        return edition_reference_id(best)

    return listed_edition_refs[0] if listed_edition_refs else None


def visible_edition_ids_for_book(
    listed_edition_refs: List[str],
    edition_index: Dict[str, Dict[str, Any]],
    owned_edition_refs_for_book: Set[str],
) -> Tuple[Set[str], Optional[str]]:
    """
    New buyer (no owned editions for this book): current listed edition only.
    Previous buyer: every owned edition still listed + current edition.
    """
    current_ref = pick_current_edition_reference(listed_edition_refs, edition_index)
    listed = set(listed_edition_refs)

    if not owned_edition_refs_for_book:
        if current_ref:
            return {current_ref}, current_ref
        return listed, None

    visible = {ref for ref in owned_edition_refs_for_book if ref in listed}
    if current_ref:
        visible.add(current_ref)
    if not visible:
        visible = {current_ref} if current_ref else listed
    return visible, current_ref


def _edition_display_role(user_owns: bool, is_current: bool) -> str:
    if user_owns and is_current:
        return "OWNED_CURRENT"
    if user_owns:
        return "OWNED"
    return "CURRENT"


def filter_store_rows_for_visibility(
    rows: List[Dict[str, Any]],
    edition_index: Dict[str, Dict[str, Any]],
    owned_editions: Set[str],
    owned_by_book: Dict[str, Set[str]],
) -> List[Dict[str, Any]]:
    by_book: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    orphans: List[Dict[str, Any]] = []

    for row in rows:
        book_ref = row.get("book_reference_id")
        if book_ref:
            by_book[str(book_ref)].append(row)
        else:
            orphans.append(row)

    visible_rows: List[Dict[str, Any]] = []

    for book_ref, group in by_book.items():
        listed_refs = [str(r["edition_reference_id"]) for r in group if r.get("edition_reference_id")]
        owned_for_book = owned_by_book.get(book_ref, set())
        visible_ids, current_ref = visible_edition_ids_for_book(
            listed_refs,
            edition_index,
            owned_for_book,
        )

        for row in group:
            ref = str(row.get("edition_reference_id") or "")
            is_current = bool(current_ref and ref == current_ref)
            owns = ref in owned_editions
            row = dict(row)
            row["is_current_edition"] = is_current
            row["edition_display_role"] = _edition_display_role(owns, is_current)
            row["show_in_store"] = ref in visible_ids
            if row["show_in_store"]:
                visible_rows.append(row)

    for row in orphans:
        row = dict(row)
        row["is_current_edition"] = None
        row["edition_display_role"] = "CURRENT"
        row["show_in_store"] = True
        visible_rows.append(row)

    return visible_rows


def is_edition_visible_in_store(
    edition_reference_id: str,
    book_reference_id: Optional[str],
    listed_edition_refs_for_book: List[str],
    edition_index: Dict[str, Dict[str, Any]],
    owned_by_book: Dict[str, Set[str]],
) -> bool:
    if not book_reference_id:
        return True
    owned_for_book = owned_by_book.get(str(book_reference_id), set())
    visible_ids, _ = visible_edition_ids_for_book(
        listed_edition_refs_for_book,
        edition_index,
        owned_for_book,
    )
    return str(edition_reference_id) in visible_ids
