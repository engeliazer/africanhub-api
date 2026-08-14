import re
import secrets
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from certificates.models.models import Salutation
from certificates.services.participant_service import get_salutation_by_id
from events.models.models import EventLetterRequest
from events.services.phone_utils import normalize_phone, PHONE_RE
from public.controllers.sms_controller import SMSService

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def build_core_name(first_name: str, middle_name: Optional[str], last_name: str) -> str:
    parts = [first_name.strip()]
    if middle_name and middle_name.strip():
        parts.append(middle_name.strip())
    parts.append(last_name.strip())
    return " ".join(part for part in parts if part)


def build_letter_invitee_full_name(
    first_name: str,
    middle_name: Optional[str],
    last_name: str,
    salutation: Optional[Salutation],
) -> str:
    core_name = build_core_name(first_name, middle_name, last_name)
    if salutation and salutation.label and salutation.label.lower() != "none":
        return f"{salutation.label} {core_name}".strip()
    return core_name


def generate_verification_code() -> str:
    """Random numeric 6-digit code (100000–999999)."""
    return str(secrets.randbelow(900_000) + 100_000)


def verification_codes_match(stored: Optional[str], submitted: str) -> bool:
    stored_value = (stored or "").strip()
    submitted_value = (submitted or "").strip()
    if not stored_value or not submitted_value:
        return False
    return stored_value.zfill(6) == submitted_value.zfill(6)


def is_verification_required(row: EventLetterRequest) -> bool:
    """Letter is blocked while both phone and email are unverified."""
    return not row.phone_verified and not row.email_verified


def validate_letter_request_payload(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    first_name = (data.get("first_name") or "").strip()
    middle_name = (data.get("middle_name") or "").strip() or None
    last_name = (data.get("last_name") or "").strip()
    organization = (data.get("organization") or "").strip()
    address = (data.get("address") or "").strip()
    email = (data.get("email") or "").strip()
    phone = normalize_phone(data.get("phone") or "")
    salutation_id = data.get("salutation_id")

    if not first_name:
        return None, "first_name is required"
    if not last_name:
        return None, "last_name is required"
    if not organization:
        return None, "organization is required"
    if not address:
        return None, "address is required"
    if not email:
        return None, "email is required"
    if not EMAIL_RE.match(email):
        return None, "Invalid email address"
    if not phone:
        return None, "phone is required"
    if not PHONE_RE.match(phone):
        return None, "Invalid phone number (use a valid Tanzania mobile number)"
    if salutation_id in (None, ""):
        return None, "salutation_id is required"
    try:
        salutation_id = int(salutation_id)
    except (TypeError, ValueError):
        return None, "salutation_id must be an integer"

    return {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "organization": organization,
        "address": address,
        "email": email.lower(),
        "phone": phone,
        "salutation_id": salutation_id,
    }, None


def validate_phone_verification_payload(
    data: Dict[str, Any],
    *,
    require_code: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    raw_id = data.get("id") if data.get("id") is not None else data.get("letter_request_id")
    code = (data.get("verification_code") or data.get("code") or "").strip()

    if raw_id in (None, ""):
        return None, "id is required"
    try:
        letter_request_id = int(raw_id)
    except (TypeError, ValueError):
        return None, "id must be an integer"
    if letter_request_id <= 0:
        return None, "id must be a positive integer"
    if require_code:
        if not code or not code.isdigit() or len(code) != 6:
            return None, "verification_code must be a 6-digit number"

    return {
        "id": letter_request_id,
        "verification_code": code.zfill(6) if code else None,
    }, None


def get_salutation_or_error(
    db: Session,
    salutation_id: int,
) -> Tuple[Optional[Salutation], Optional[str]]:
    row = get_salutation_by_id(db, salutation_id)
    if not row:
        return None, f"Salutation {salutation_id} not found or inactive"
    return row, None


def find_existing_letter_request(
    db: Session,
    event_id: int,
    email: str,
    phone: str,
) -> Optional[EventLetterRequest]:
    return (
        db.query(EventLetterRequest)
        .filter(
            EventLetterRequest.event_id == event_id,
            (
                (EventLetterRequest.email == email)
                | (EventLetterRequest.phone == phone)
            ),
        )
        .first()
    )


def find_letter_request_by_id(
    db: Session,
    event_id: int,
    letter_request_id: int,
) -> Optional[EventLetterRequest]:
    return (
        db.query(EventLetterRequest)
        .filter(
            EventLetterRequest.id == letter_request_id,
            EventLetterRequest.event_id == event_id,
        )
        .first()
    )


def send_phone_verification_sms(phone: str, code: str, first_name: str) -> Tuple[bool, str]:
    message = (
        f"Dear {first_name},\n"
        f"Your African Hub verification code for course invitation letter is {code}. "
        "Do not share this code."
    )
    result = SMSService.send_message(
        phone=phone,
        message=message,
        process_name="event_letter_phone_verify",
    )
    if result.get("success"):
        return True, result.get("message") or "Verification code sent"
    return False, result.get("message") or "Failed to send verification SMS"


def build_invitee_from_letter_request(
    letter_request: EventLetterRequest,
    salutation: Optional[Salutation],
) -> Dict[str, str]:
    return {
        "full_name": build_letter_invitee_full_name(
            letter_request.first_name,
            letter_request.middle_name,
            letter_request.last_name,
            salutation,
        ),
        "organization": letter_request.organization,
        "address": letter_request.address,
        "email": letter_request.email,
    }


def letter_request_to_dict(
    row: EventLetterRequest,
    *,
    salutation: Optional[Salutation] = None,
    event: Any = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": row.id,
        "event_id": row.event_id,
        "first_name": row.first_name,
        "middle_name": row.middle_name,
        "last_name": row.last_name,
        "full_name": build_letter_invitee_full_name(
            row.first_name,
            row.middle_name,
            row.last_name,
            salutation,
        ),
        "salutation_id": row.salutation_id,
        "salutation": salutation.label if salutation else None,
        "organization": row.organization,
        "address": row.address,
        "email": row.email,
        "phone": row.phone,
        "phone_verification_code": row.phone_verification_code,
        "email_verification_code": row.email_verification_code,
        "phone_verified": bool(row.phone_verified),
        "email_verified": bool(row.email_verified),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if event is not None:
        payload["event_title"] = event.title
        payload["course_title"] = event.course_title
    return payload
