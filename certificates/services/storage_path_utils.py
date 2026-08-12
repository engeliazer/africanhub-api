import os
from typing import Optional
from urllib.parse import urlparse

from config import PUBLIC_STORAGE_BASE_URL, UPLOAD_FOLDER


def storage_url_to_local_path(url: Optional[str]) -> Optional[str]:
    """Map a public /storage/... URL (or full API URL) to a local upload path."""
    if not url:
        return None

    text = url.strip()
    if not text:
        return None

    if text.startswith("/storage/"):
        relative = text[len("/storage/") :]
        return os.path.join(UPLOAD_FOLDER, relative.replace("/", os.sep))

    parsed = urlparse(text)
    path = parsed.path or ""
    storage_prefix = urlparse(PUBLIC_STORAGE_BASE_URL).path.rstrip("/")
    if storage_prefix and path.startswith(storage_prefix + "/"):
        relative = path[len(storage_prefix) + 1 :]
        return os.path.join(UPLOAD_FOLDER, relative.replace("/", os.sep))

    if path.startswith("/storage/"):
        relative = path[len("/storage/") :]
        return os.path.join(UPLOAD_FOLDER, relative.replace("/", os.sep))

    return None
