import os
import re
import uuid
from typing import Optional, Tuple

from werkzeug.datastructures import FileStorage

from config import UPLOAD_FOLDER, public_storage_url

TRAINING_LOGOS_DIR = "certificate_trainings/logos"
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB


def _safe_slug(value: str, fallback: str = "training") -> str:
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


def handle_training_logo_upload(
    file_storage: FileStorage,
    training_type: str,
    training_id: int,
    slot: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Save host or invited training logo PNG/JPG.
    Returns (public_url, error_message).
    """
    if not file_storage or not file_storage.filename:
        return None, None

    if "." not in file_storage.filename:
        return None, "Invalid logo file name"

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return None, "Invalid logo type. Allowed: PNG, JPG, JPEG"

    size_error = _validate_file_size(file_storage, MAX_LOGO_BYTES)
    if size_error:
        return None, size_error

    directory = os.path.join(UPLOAD_FOLDER, TRAINING_LOGOS_DIR)
    os.makedirs(directory, exist_ok=True)

    filename = (
        f"{_safe_slug(training_type)}-{training_id}-"
        f"{_safe_slug(slot)}-{uuid.uuid4().hex[:8]}.{ext}"
    )
    file_storage.save(os.path.join(directory, filename))

    return public_storage_url(TRAINING_LOGOS_DIR, filename), None
