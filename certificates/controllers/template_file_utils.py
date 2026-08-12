import os
import re
import uuid
from typing import Optional, Tuple

from werkzeug.datastructures import FileStorage

from config import UPLOAD_FOLDER, public_storage_url

BACKGROUNDS_DIR = "certificate_templates/backgrounds"
SIGNATURES_DIR = "certificate_templates/signatures"
ALLOWED_BACKGROUND_EXTENSIONS = {"pdf"}
ALLOWED_SIGNATURE_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_BACKGROUND_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_SIGNATURE_BYTES = 5 * 1024 * 1024  # 5 MB


def _safe_slug(value: str, fallback: str = "template") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "-", (value or fallback).lower()).strip("-")
    return slug or fallback


def _validate_file_size(file_storage: FileStorage, max_bytes: int) -> Optional[str]:
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return "File is empty"
    if size > max_bytes:
        return f"File must be {max_bytes // (1024 * 1024)}MB or smaller"
    return None


def handle_background_upload(
    file_storage: FileStorage,
    template_name: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Save certificate background PDF.
    Returns (public_url, original_filename, error_message).
    """
    if not file_storage or not file_storage.filename:
        return None, None, "Background PDF is required"

    if "." not in file_storage.filename:
        return None, None, "Invalid background file name"

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_BACKGROUND_EXTENSIONS:
        return None, None, "Invalid background type. Allowed: PDF"

    size_error = _validate_file_size(file_storage, MAX_BACKGROUND_BYTES)
    if size_error:
        return None, None, size_error

    directory = os.path.join(UPLOAD_FOLDER, BACKGROUNDS_DIR)
    os.makedirs(directory, exist_ok=True)

    filename = f"{_safe_slug(template_name)}-{uuid.uuid4().hex[:8]}.{ext}"
    file_storage.save(os.path.join(directory, filename))

    return public_storage_url(BACKGROUNDS_DIR, filename), file_storage.filename, None


def handle_signature_upload(
    file_storage: FileStorage,
    template_name: str,
    display_order: int,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Save signatory signature image.
    Returns (public_url, error_message).
    """
    if not file_storage or not file_storage.filename:
        return None, None

    if "." not in file_storage.filename:
        return None, "Invalid signature file name"

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_SIGNATURE_EXTENSIONS:
        return None, "Invalid signature type. Allowed: PNG, JPG, JPEG"

    size_error = _validate_file_size(file_storage, MAX_SIGNATURE_BYTES)
    if size_error:
        return None, size_error

    directory = os.path.join(UPLOAD_FOLDER, SIGNATURES_DIR)
    os.makedirs(directory, exist_ok=True)

    filename = f"{_safe_slug(template_name)}-sig{display_order}-{uuid.uuid4().hex[:8]}.{ext}"
    file_storage.save(os.path.join(directory, filename))

    return public_storage_url(SIGNATURES_DIR, filename), None
