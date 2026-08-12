import os
import urllib.error
import urllib.request
from typing import Optional, Tuple
from urllib.parse import urlparse

from config import API_BASE_URL, PUBLIC_STORAGE_BASE_URL, UPLOAD_FOLDER


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


def is_same_api_host(url: str) -> bool:
    if not url:
        return False
    target = urlparse(url.strip())
    api = urlparse(API_BASE_URL)
    if not target.netloc:
        return True
    return target.netloc.lower() == api.netloc.lower()


def read_storage_asset_bytes(url: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Load a file from local storage/uploads. Never HTTP-fetches same-host /storage URLs
    (avoids gunicorn self-deadlock). External URLs are fetched with urllib.
    """
    if not url or not str(url).strip():
        return None, "Asset URL is empty"

    local_path = storage_url_to_local_path(url)
    if local_path:
        if os.path.isfile(local_path):
            with open(local_path, "rb") as handle:
                return handle.read(), None
        if is_same_api_host(url) or str(url).strip().startswith("/storage/"):
            return None, f"Storage file not found on server: {local_path}"

    if is_same_api_host(url):
        return None, f"Could not resolve local path for storage URL: {url}"

    try:
        request = urllib.request.Request(
            url.strip(),
            headers={"User-Agent": "africanhub-api/1.0"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read(), None
    except urllib.error.URLError as exc:
        return None, f"Could not fetch asset URL {url}: {exc}"
    except Exception as exc:
        return None, f"Could not load asset URL {url}: {exc}"
