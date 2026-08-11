import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple

from flask import request
from werkzeug.datastructures import FileStorage

from config import UPLOAD_FOLDER, public_storage_url

ALLOWED_SUBJECT_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "txt"}
MAX_SUBJECT_DOCUMENT_BYTES = 15 * 1024 * 1024  # 15 MB

SUBJECT_DOCUMENTS_DIR = "subject_documents"


def _parse_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _parse_int_optional(value) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def handle_subject_details_document_upload(
    file_storage: FileStorage,
    subject_code: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Save subject details document. Returns (public_url, error_message).
    """
    if not file_storage or not file_storage.filename:
        return None, None

    if "." not in file_storage.filename:
        return None, "Invalid file name"

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_SUBJECT_DOCUMENT_EXTENSIONS:
        return None, (
            "Invalid document type. Allowed: PDF, DOC, DOCX, TXT"
        )

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_SUBJECT_DOCUMENT_BYTES:
        return None, "Document must be 15MB or smaller"
    if size == 0:
        return None, "Document file is empty"

    directory = os.path.join(UPLOAD_FOLDER, SUBJECT_DOCUMENTS_DIR)
    os.makedirs(directory, exist_ok=True)

    safe_code = re.sub(r"[^a-zA-Z0-9]", "-", (subject_code or "subject").lower()).strip("-") or "subject"
    filename = f"{safe_code}-{uuid.uuid4().hex[:8]}.{ext}"
    file_storage.save(os.path.join(directory, filename))

    return public_storage_url(SUBJECT_DOCUMENTS_DIR, filename), None


def delete_subject_details_document(url: Optional[str]) -> None:
    if not url:
        return
    marker = f"/{SUBJECT_DOCUMENTS_DIR}/"
    if marker not in url:
        return
    filename = url.split(marker, 1)[-1].split("?", 1)[0]
    if not filename:
        return
    path = os.path.join(UPLOAD_FOLDER, SUBJECT_DOCUMENTS_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)


def parse_subject_create_payload() -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Parse JSON or multipart create payload.
    Returns (data dict, error_message, http_status_code as string '400'|None).
    """
    if request_has_form():
        user_id = request.form.get("created_by") or request.form.get("updated_by")
        if not user_id:
            return None, "created_by and updated_by are required", "400"

        data = {
            "name": request.form.get("name"),
            "code": request.form.get("code"),
            "description": request.form.get("description"),
            "current_price": _parse_int_optional(request.form.get("current_price")),
            "duration_days": _parse_int_optional(request.form.get("duration_days")),
            "trial_duration_days": _parse_int_optional(request.form.get("trial_duration_days")),
            "display_rank": _parse_int_optional(request.form.get("display_rank")),
            "is_most_popular": _parse_bool(request.form.get("is_most_popular")),
            "is_best_price": _parse_bool(request.form.get("is_best_price")),
            "is_most_recent": _parse_bool(request.form.get("is_most_recent")),
            "is_active": _parse_bool(request.form.get("is_active"), default=True),
            "created_by": int(user_id),
            "updated_by": int(request.form.get("updated_by") or user_id),
        }
        return data, None, None

    data = request.get_json(silent=True)
    if not data:
        return None, "Request body is required", "400"
    return data, None, None


def parse_subject_update_payload() -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    if request_has_form():
        data = {}
        for field in (
            "name", "code", "description", "current_price", "duration_days",
            "trial_duration_days", "display_rank", "updated_by",
        ):
            if field in request.form and request.form.get(field) not in (None, ""):
                if field in ("current_price", "duration_days", "trial_duration_days", "display_rank"):
                    data[field] = _parse_int_optional(request.form.get(field))
                elif field == "updated_by":
                    data[field] = int(request.form.get(field))
                else:
                    data[field] = request.form.get(field)

        for field in ("is_most_popular", "is_best_price", "is_most_recent", "is_active"):
            if field in request.form:
                data[field] = _parse_bool(request.form.get(field))

        if "updated_by" not in data:
            return None, "updated_by is required", "400"
        return data, None, None

    data = request.get_json(silent=True)
    if not data:
        return None, "Request body is required", "400"
    return data, None, None


def request_has_form() -> bool:
    return bool(request.form) or bool(request.files)


def get_details_document_file():
    return request.files.get("details_document")


def should_remove_details_document() -> bool:
    return _parse_bool(request.form.get("remove_details_document"))


def replace_subject_details_document(
    subject,
    doc_file: FileStorage,
) -> Tuple[Optional[str], Optional[str]]:
    """Upload a new details document for a subject, replacing any existing file."""
    details_document_url, upload_error = handle_subject_details_document_upload(
        doc_file,
        getattr(subject, "code", None) or "subject",
    )
    if upload_error:
        return None, upload_error
    if not details_document_url:
        return None, "Details document file is required"

    delete_subject_details_document(getattr(subject, "details_document_url", None))
    return details_document_url, None
