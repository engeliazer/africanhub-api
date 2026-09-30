import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from werkzeug.utils import secure_filename

from config import BASE_DIR

MAX_BYTES = int(os.getenv("BOOK_PAYMENT_ATTACHMENT_MAX_MB", "10")) * 1024 * 1024
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

UPLOAD_DIR = Path(
    os.getenv(
        "BOOK_PAYMENT_UPLOAD_DIR",
        os.path.join(BASE_DIR, "storage", "uploads", "book_payments"),
    )
)


def validate_payment_attachment(file_storage) -> Optional[str]:
    if not file_storage or not file_storage.filename:
        return "Proof of payment attachment is required"

    name = file_storage.filename.lower()
    ext = os.path.splitext(name)[1]
    if ext not in ALLOWED_EXT:
        return "Allowed attachment types: PDF, PNG, JPG, WEBP"

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return "Attachment is empty"
    if size > MAX_BYTES:
        return f"Attachment must be {MAX_BYTES // (1024 * 1024)}MB or smaller"
    return None


def save_payment_attachment(order_id: int, file_storage) -> Tuple[str, str]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original = secure_filename(file_storage.filename)
    ext = os.path.splitext(original)[1].lower()
    stored = f"order-{order_id}-{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / stored
    file_storage.save(str(path))
    relative = f"book_payments/{stored}"
    return relative, original
