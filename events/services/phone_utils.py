import re

TZ_COUNTRY_CODE = "255"
PHONE_RE = re.compile(r"^255\d{9}$")


def normalize_phone(value: str) -> str:
    """Strip non-digits, take last 9 digits, prefix 255."""
    digits = re.sub(r"\D", "", (value or "").strip())
    if len(digits) < 9:
        return ""
    return f"{TZ_COUNTRY_CODE}{digits[-9:]}"
