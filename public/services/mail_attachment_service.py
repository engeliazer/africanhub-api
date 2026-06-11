"""
PDF attachment handling for mail batches (PDF only).
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from werkzeug.utils import secure_filename

from config import BASE_DIR

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
MAX_PDF_BYTES = int(os.getenv("MAIL_ATTACHMENT_MAX_MB", "15")) * 1024 * 1024

MAIL_BATCH_UPLOAD_DIR = Path(
    os.getenv(
        "MAIL_BATCH_UPLOAD_DIR",
        os.path.join(BASE_DIR, "storage", "uploads", "mail_batches"),
    )
)


def _ensure_upload_dir(batch_id: int) -> Path:
    directory = MAIL_BATCH_UPLOAD_DIR / str(batch_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def validate_pdf_upload(file_storage) -> Optional[str]:
    """Return error message if invalid, None if OK or no file provided."""
    if not file_storage or not file_storage.filename:
        return None

    filename = file_storage.filename
    if not filename.lower().endswith(".pdf"):
        return "Only PDF attachments are allowed"

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_PDF_BYTES:
        max_mb = MAX_PDF_BYTES // (1024 * 1024)
        return f"PDF attachment must be {max_mb}MB or smaller"
    if size == 0:
        return "PDF attachment is empty"

    header = file_storage.stream.read(4)
    file_storage.stream.seek(0)
    if header != PDF_MAGIC:
        return "File is not a valid PDF"

    return None


def save_batch_pdf(batch_id: int, file_storage) -> Tuple[str, str]:
    """
    Save uploaded PDF for a batch.

    Returns:
        (absolute_path, original_filename)
    """
    original_name = secure_filename(file_storage.filename) or "attachment.pdf"
    if not original_name.lower().endswith(".pdf"):
        original_name = f"{original_name}.pdf"

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    directory = _ensure_upload_dir(batch_id)
    dest = directory / stored_name
    file_storage.save(str(dest))
    logger.info("Saved mail batch %s PDF attachment to %s", batch_id, dest)
    return str(dest), original_name


def read_batch_pdf(attachment_path: str) -> bytes:
    path = Path(attachment_path)
    if not path.is_file():
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")
    return path.read_bytes()
