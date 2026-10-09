"""
Additional PDF attachment (e.g. Course Contents) sent with every invitation email.
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

# Sent alongside the generated letter in every email; SES rejects messages over 10MB
# after base64 encoding, so keep this well below that.
MAX_ATTACHMENT_BYTES = int(os.getenv("INVITATION_ATTACHMENT_MAX_MB", "5")) * 1024 * 1024

ATTACHMENT_DIR = Path(
    os.getenv(
        "INVITATION_ATTACHMENT_DIR",
        os.path.join(BASE_DIR, "storage", "uploads", "invitation_attachments"),
    )
)


def validate_invitation_attachment(file_storage) -> Optional[str]:
    if not file_storage or not file_storage.filename:
        return "PDF file is required (field: attachment)"
    if not file_storage.filename.lower().endswith(".pdf"):
        return "Only PDF files are allowed"

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return "PDF file is empty"
    if size > MAX_ATTACHMENT_BYTES:
        return f"PDF must be {MAX_ATTACHMENT_BYTES // (1024 * 1024)}MB or smaller"

    header = file_storage.stream.read(4)
    file_storage.stream.seek(0)
    if header != PDF_MAGIC:
        return "File is not a valid PDF"
    return None


def save_invitation_attachment(invitation_id: int, file_storage) -> Tuple[str, str]:
    original_name = secure_filename(file_storage.filename) or "attachment.pdf"
    if not original_name.lower().endswith(".pdf"):
        original_name = f"{original_name}.pdf"
    directory = ATTACHMENT_DIR / str(invitation_id)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{uuid.uuid4().hex}_{original_name}"
    file_storage.save(str(dest))
    logger.info("Saved additional attachment for invitation %s at %s", invitation_id, dest)
    return str(dest), original_name


def delete_invitation_attachment_file(attachment_path: Optional[str]) -> None:
    if not attachment_path:
        return
    path = Path(attachment_path)
    if path.is_file():
        path.unlink()
        logger.info("Removed invitation attachment %s", path)
