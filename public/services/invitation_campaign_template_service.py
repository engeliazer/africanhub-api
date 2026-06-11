"""
Custom Jinja2 HTML template upload for invitation campaigns.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from werkzeug.utils import secure_filename

from config import BASE_DIR

logger = logging.getLogger(__name__)

MAX_TEMPLATE_BYTES = int(os.getenv("INVITATION_TEMPLATE_MAX_MB", "2")) * 1024 * 1024

CAMPAIGN_TEMPLATE_DIR = Path(
    os.getenv(
        "INVITATION_CAMPAIGN_TEMPLATE_DIR",
        os.path.join(BASE_DIR, "storage", "uploads", "invitation_campaign_templates"),
    )
)

# Custom templates should reference at least the invitee name in Jinja2 syntax.
REQUIRED_JINJA_MARKERS = ("invitee.full_name", "{{ invitee")


def _ensure_dir(invitation_id: int) -> Path:
    directory = CAMPAIGN_TEMPLATE_DIR / str(invitation_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def validate_campaign_template_upload(file_storage) -> Optional[str]:
    if not file_storage or not file_storage.filename:
        return "HTML invitation template is required"

    filename = file_storage.filename.lower()
    if not (filename.endswith(".html") or filename.endswith(".htm")):
        return "Invitation template must be an HTML file (.html or .htm)"

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_TEMPLATE_BYTES:
        return f"Template must be {MAX_TEMPLATE_BYTES // (1024 * 1024)}MB or smaller"
    if size == 0:
        return "Template file is empty"

    content = file_storage.stream.read().decode("utf-8", errors="ignore")
    file_storage.stream.seek(0)
    lower = content.lower()
    if "<html" not in lower and "<body" not in lower:
        return "File does not appear to be valid HTML"

    if not any(marker in content for marker in REQUIRED_JINJA_MARKERS):
        return (
            "Template must be a Jinja2 HTML file and include invitee.full_name "
            "(e.g. {{ invitee.full_name }})"
        )

    return None


def save_campaign_template(invitation_id: int, file_storage) -> Tuple[str, str]:
    original_name = secure_filename(file_storage.filename) or "invitation_template.html"
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    directory = _ensure_dir(invitation_id)
    dest = directory / stored_name
    file_storage.save(str(dest))
    logger.info("Saved invitation campaign template for %s at %s", invitation_id, dest)
    return str(dest), original_name


def delete_campaign_template_file(template_path: Optional[str]) -> None:
    if not template_path:
        return
    path = Path(template_path)
    if path.is_file():
        path.unlink()
        logger.info("Removed invitation campaign template %s", path)
