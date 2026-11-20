"""Optional cover image for a promotional video."""

import os
import uuid

from config import UPLOAD_FOLDER, public_storage_url

ALLOWED_COVER_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


def save_promo_cover(cover_file):
    """Store an uploaded cover and return (public_url, error_message)."""
    filename = getattr(cover_file, "filename", "") or ""
    if "." not in filename:
        return None, "Cover must be a JPG, PNG, GIF, or WebP image"

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_COVER_EXTENSIONS:
        return None, "Cover must be a JPG, PNG, GIF, or WebP image"

    directory = os.path.join(UPLOAD_FOLDER, "promo_videos")
    os.makedirs(directory, exist_ok=True)
    stored_name = f"cover-{uuid.uuid4().hex[:12]}.{extension}"
    cover_file.save(os.path.join(directory, stored_name))
    return public_storage_url("promo_videos", stored_name), None
