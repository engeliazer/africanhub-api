"""Public certificate verification URL helpers (no DB imports)."""

from urllib.parse import quote

from config import API_BASE_URL, CERTIFICATE_VERIFY_BASE_URL


def build_verification_view_url(serial_no: str) -> str:
    encoded = quote((serial_no or "").strip(), safe="")
    return f"{CERTIFICATE_VERIFY_BASE_URL}?serial_no={encoded}"


def build_verification_pdf_url(serial_no: str) -> str:
    encoded = quote((serial_no or "").strip(), safe="")
    return f"{API_BASE_URL}/api/certificates/public/verify/pdf?serial_no={encoded}"
