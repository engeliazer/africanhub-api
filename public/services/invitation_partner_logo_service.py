"""
Training partner logo upload for invitation campaigns.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from werkzeug.utils import secure_filename

from config import BASE_DIR

logger = logging.getLogger(__name__)

MAX_LOGO_BYTES = int(os.getenv("INVITATION_PARTNER_LOGO_MAX_MB", "2")) * 1024 * 1024

# xhtml2pdf cannot render SVG, so only raster formats are accepted.
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

PARTNER_LOGO_DIR = Path(
    os.getenv(
        "INVITATION_PARTNER_LOGO_DIR",
        os.path.join(BASE_DIR, "storage", "uploads", "invitation_partner_logos"),
    )
)


def validate_partner_logo_upload(file_storage) -> Optional[str]:
    if not file_storage or not file_storage.filename:
        return "Partner logo file is required (field: logo)"

    suffix = Path(file_storage.filename).suffix.lower()
    if suffix not in ALLOWED_LOGO_EXTENSIONS:
        return "Partner logo must be PNG, JPG, GIF or WEBP"

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return "Partner logo file is empty"
    if size > MAX_LOGO_BYTES:
        return f"Partner logo must be {MAX_LOGO_BYTES // (1024 * 1024)}MB or smaller"
    return None


def save_partner_logo(invitation_id: int, file_storage) -> Tuple[str, str]:
    original_name = secure_filename(file_storage.filename) or "partner_logo.png"
    directory = PARTNER_LOGO_DIR / str(invitation_id)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{uuid.uuid4().hex}_{original_name}"
    file_storage.save(str(dest))
    logger.info("Saved partner logo for invitation %s at %s", invitation_id, dest)
    return str(dest), original_name


def resolve_partner_logo_path(logo_path: Optional[str]) -> Optional[Path]:
    if not logo_path:
        return None
    path = Path(logo_path)
    if not path.is_absolute():
        path = Path(BASE_DIR) / path
    return path if path.is_file() else None


def delete_partner_logo_file(logo_path: Optional[str]) -> None:
    """Delete an uploaded logo; shared files outside the upload folder are left alone."""
    path = resolve_partner_logo_path(logo_path)
    if not path:
        return
    try:
        path.resolve().relative_to(PARTNER_LOGO_DIR.resolve())
    except ValueError:
        return
    path.unlink()
    logger.info("Removed partner logo %s", path)
