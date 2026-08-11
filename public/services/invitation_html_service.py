"""
Jinja2 HTML generation for full invitation campaigns (7 sections).
"""

import base64
import html
import os
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from applications.models.models import Invitation, InvitationTrainer
from config import BASE_DIR
from public.services.mail_service import NAME_PLACEHOLDER

BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_TEMPLATE = "invitations/invitation_letter.html"

SAMPLE_INVITEE = {
    "full_name": "John Doe",
    "email": "john.doe@example.com",
    "address": "123 Sample Street\nDar es Salaam, Tanzania",
    "organization": "Sample Organization Ltd",
}

_jinja_env: Optional[Environment] = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        def _normalize_line_breaks(value) -> str:
            if value is None:
                return ""
            text = str(value)
            text = BR_TAG_RE.sub("\n", text)
            return text

        def nl2br(value) -> Markup:
            """Newlines and <br> tags → HTML line breaks (safe for PDF rendering)."""
            text = html.escape(_normalize_line_breaks(value))
            return Markup(text.replace("\n", "<br />"))

        def richtext(value) -> Markup:
            """Paragraphs + line breaks; safe for invitee-personalized message HTML."""
            text = html.escape(_normalize_line_breaks(value).strip())
            if not text:
                return Markup("")
            paragraphs = re.split(r"\n\s*\n", text)
            blocks = [
                f'<p class="letter-message-p">'
                f'{para.replace(chr(10), "<br />")}'
                f"</p>"
                for para in paragraphs
                if para.strip()
            ]
            return Markup("".join(blocks))

        env.filters["nl2br"] = nl2br
        env.filters["richtext"] = richtext
        _jinja_env = env
    return _jinja_env


def _format_date(value: Optional[date]) -> Optional[str]:
    if not value:
        return None
    return value.strftime("%d %B %Y")


def _format_time(value: Optional[time]) -> Optional[str]:
    if not value:
        return None
    return value.strftime("%H:%M")


def _format_money(amount) -> Optional[str]:
    if amount is None:
        return None
    return f"TZS {float(amount):,.2f}"


def _ordinal_day(day: int) -> str:
    if 11 <= (day % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _format_letter_date(value: Optional[date] = None) -> str:
    """e.g. 20th May 2026"""
    d = value or datetime.utcnow().date()
    return f"{_ordinal_day(d.day)} {d.strftime('%B %Y')}"


def _letter_reference(invitation_id: int, ref_date: Optional[date] = None) -> str:
    d = ref_date or datetime.utcnow().date()
    return f"AHB&T/{d.strftime('%m/%y')}/{int(invitation_id):07d}"


def _invitee_addressee_parts(invitee: Dict[str, Any]) -> tuple:
    """Organization and address suffix for formal addressee line."""
    organization = (invitee.get("organization") or "").strip().rstrip(".")
    address = (invitee.get("address") or "").strip()
    address_line = address.splitlines()[0].strip().rstrip(".") if address else ""
    if organization and address_line and address_line.lower() in organization.lower():
        address_line = ""
    return organization, address_line


def _invitee_addressee_line(invitee: Dict[str, Any]) -> str:
    """Formal line under salutation, e.g. 'Sub Treasury, Rukwa.'"""
    organization, address_line = _invitee_addressee_parts(invitee)
    if organization and address_line:
        return f"{organization}, {address_line}."
    if organization:
        return f"{organization}."
    if address_line:
        return f"{address_line}."
    return ""


def _personalize_text(text: Optional[str], full_name: str) -> str:
    return (text or "").replace(NAME_PLACEHOLDER, full_name or "")


def _subject_heading(course_title: str) -> str:
    title = (course_title or "").strip().upper()
    if title.startswith("RE:"):
        return title
    return f"RE: AN INVITATION TO {title}"


def _watermark_opacity() -> float:
    try:
        value = float((os.getenv("MAIL_WATERMARK_OPACITY") or "0.2").strip())
        return max(0.0, min(1.0, value))
    except (TypeError, ValueError):
        return 0.2


def _signatory_image_url(env_var: str, default_relative: str) -> str:
    """Resolve a signatory image to a URL xhtml2pdf can load (data URI or http)."""
    raw = (os.getenv(env_var) or default_relative).strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://", "data:")):
        return raw

    path = Path(raw)
    if not path.is_absolute():
        path = Path(BASE_DIR) / raw
    if not path.is_file():
        return ""

    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _signatory_context() -> Dict[str, str]:
    return {
        "name": (os.getenv("MAIL_SIGNATORY_NAME") or "Dr. CPA David D Kiwia").strip(),
        "credentials": (
            os.getenv("MAIL_SIGNATORY_CREDENTIALS")
            or "PhD-Finance, ACPA-PP, MFA-OG, BAF, IPSAS"
        ).strip(),
        "title": (os.getenv("MAIL_SIGNATORY_TITLE") or "Managing Director").strip(),
        "signature_url": _signatory_image_url(
            "MAIL_SIGNATURE_IMAGE_PATH",
            "storage/images/mdsignature.png",
        ),
        "stamp_url": _signatory_image_url(
            "MAIL_STAMP_IMAGE_PATH",
            "storage/images/stamp.png",
        ),
    }


def _brand_context(invitation: Optional[Invitation] = None) -> Dict[str, str]:
    logo = (os.getenv("MAIL_LOGO_URL") or "https://africanhub.ac.tz/logo.png").strip()
    letterhead_logo = (os.getenv("MAIL_LETTERHEAD_LOGO_URL") or logo).strip()
    source_email = getattr(invitation, "source_email", None) if invitation else None
    return {
        "name": (os.getenv("MAIL_FROM_NAME") or "The African Hub").strip().upper(),
        "legal_name": (
            os.getenv("MAIL_BRAND_LEGAL_NAME")
            or "AFRICAN HUB OF BUSINESS & TECHNOLOGY"
        ).strip().upper(),
        "tagline": (
            os.getenv("MAIL_BRAND_TAGLINE") or "Building Accounting Skills for the Real World"
        ).strip(),
        "logo_url": logo,
        "letterhead_logo_url": letterhead_logo,
        "watermark_opacity": _watermark_opacity(),
        "po_box": (
            os.getenv("MAIL_BRAND_PO_BOX")
            or "P. O. Box 36246, Dar es Salaam, Tanzania"
        ).strip(),
        "phone": (
            os.getenv("MAIL_BRAND_PHONE")
            or "+255 710 223 399 or +255 716 734 577"
        ).strip(),
        "info_email": (
            os.getenv("MAIL_BRAND_INFO_EMAIL")
            or "info@africanhub.ac.tz"
        ).strip(),
        "website": (os.getenv("MAIL_WEBSITE_URL") or "https://africanhub.ac.tz").strip(),
        "contact_email": (
            os.getenv("MAIL_REPLY_TO")
            or source_email
            or "trainings@africanhub.ac.tz"
        ).strip(),
    }


def _course_render_fields(
    *,
    start_date,
    end_date,
    start_time,
    end_time,
    course_title,
    course_description,
    venue,
    learning_outcomes,
    course_fee,
    deposit_amount,
    reservation_deadline,
    bank_account_name,
    bank_account_number,
    bank_name,
) -> Dict[str, Any]:
    """Shared course/payment block for invitation and event letters."""
    start_date_fmt = _format_date(start_date)
    end_date_fmt = _format_date(end_date)
    if start_date_fmt and end_date_fmt and start_date_fmt != end_date_fmt:
        date_range = f"{start_date_fmt} – {end_date_fmt}"
    else:
        date_range = start_date_fmt or end_date_fmt or ""

    start_time_fmt = _format_time(start_time)
    end_time_fmt = _format_time(end_time)
    if start_time_fmt and end_time_fmt:
        time_range = f"{start_time_fmt} – {end_time_fmt}"
    else:
        time_range = start_time_fmt or end_time_fmt or ""

    course_fee_fmt = _format_money(course_fee)
    deposit_amount_fmt = _format_money(deposit_amount)
    has_payment = any([
        course_fee_fmt,
        deposit_amount_fmt,
        reservation_deadline,
        bank_name,
        bank_account_name,
        bank_account_number,
    ])

    return {
        "course": {
            "title": course_title,
            "description": course_description,
            "venue": venue,
            "start_date": start_date_fmt,
            "end_date": end_date_fmt,
            "date_range": date_range,
            "start_time": start_time_fmt,
            "end_time": end_time_fmt,
            "time_range": time_range,
            "learning_outcomes": _learning_outcomes_list(learning_outcomes),
        },
        "payment": {
            "course_fee": course_fee_fmt,
            "deposit_amount": deposit_amount_fmt,
            "reservation_deadline": _format_date(reservation_deadline),
            "bank_account_name": bank_account_name,
            "bank_account_number": bank_account_number,
            "bank_name": bank_name,
            "has_payment_info": has_payment,
        },
    }


def _learning_outcomes_list(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def _trainers_from_invitation(invitation: Invitation) -> List[Dict[str, Any]]:
    ordered = sorted(
        invitation.trainer_assignments,
        key=lambda a: (a.display_order, a.id),
    )
    trainers: List[Dict[str, Any]] = []
    for assignment in ordered:
        trainer: Optional[InvitationTrainer] = assignment.trainer
        if not trainer:
            continue
        trainers.append({
            "full_name": trainer.full_name,
            "designation": trainer.designation,
            "bio": trainer.bio,
            "qualifications": trainer.qualifications,
            "photo": trainer.photo,
            "display_order": assignment.display_order,
        })
    return trainers


def build_invitation_render_context(
    invitation: Invitation,
    invitee: Dict[str, Any],
    *,
    trainers: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build Jinja2 context for invitation letter rendering."""
    shared = _course_render_fields(
        start_date=invitation.start_date,
        end_date=invitation.end_date,
        start_time=invitation.start_time,
        end_time=invitation.end_time,
        course_title=invitation.course_title,
        course_description=invitation.course_description,
        venue=invitation.venue,
        learning_outcomes=invitation.learning_outcomes,
        course_fee=invitation.course_fee,
        deposit_amount=invitation.deposit_amount,
        reservation_deadline=invitation.reservation_deadline,
        bank_account_name=invitation.bank_account_name,
        bank_account_number=invitation.bank_account_number,
        bank_name=invitation.bank_name,
    )

    letter_date = _format_letter_date()
    full_name = invitee.get("full_name") or ""
    organization, address_line = _invitee_addressee_parts(invitee)
    return {
        "brand": _brand_context(invitation),
        "signatory": _signatory_context(),
        "letter": {
            "reference": _letter_reference(invitation.id),
            "date": letter_date,
            "subject_heading": _subject_heading(invitation.course_title),
        },
        "invitation": {
            "title": invitation.title,
            "email_message": _personalize_text(invitation.email_message, full_name),
            "email_subject": _personalize_text(invitation.email_subject, full_name),
        },
        "invitee": {
            "full_name": full_name,
            "email": invitee.get("email") or "",
            "address": invitee.get("address") or "",
            "organization": organization,
            "address_line": address_line,
            "addressee_line": _invitee_addressee_line(invitee),
        },
        **shared,
        "trainers": trainers if trainers is not None else _trainers_from_invitation(invitation),
    }


def build_event_render_context(
    event,
    invitee: Dict[str, Any],
    *,
    trainers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build Jinja2 context for public event invitation letters."""
    shared = _course_render_fields(
        start_date=event.start_date,
        end_date=event.end_date,
        start_time=event.start_time,
        end_time=event.end_time,
        course_title=event.course_title,
        course_description=event.course_description,
        venue=event.venue,
        learning_outcomes=event.learning_outcomes,
        course_fee=event.course_fee,
        deposit_amount=event.deposit_amount,
        reservation_deadline=event.reservation_deadline,
        bank_account_name=event.bank_account_name,
        bank_account_number=event.bank_account_number,
        bank_name=event.bank_name,
    )

    letter_date = _format_letter_date()
    full_name = invitee.get("full_name") or ""
    organization, address_line = _invitee_addressee_parts(invitee)
    return {
        "brand": _brand_context(),
        "signatory": _signatory_context(),
        "letter": {
            "reference": _letter_reference(event.id),
            "date": letter_date,
            "subject_heading": _subject_heading(event.course_title),
        },
        "invitation": {
            "title": event.title,
            "email_message": "",
            "email_subject": "",
        },
        "invitee": {
            "full_name": full_name,
            "email": invitee.get("email") or "",
            "address": invitee.get("address") or "",
            "organization": organization,
            "address_line": address_line,
            "addressee_line": _invitee_addressee_line(invitee),
        },
        **shared,
        "trainers": [
            {
                "full_name": t.get("full_name"),
                "designation": t.get("designation"),
                "bio": t.get("bio"),
                "qualifications": t.get("qualifications"),
                "photo": t.get("photo"),
            }
            for t in trainers
        ],
    }


def _is_jinja_template_file(template_path: str) -> bool:
    text = Path(template_path).read_text(encoding="utf-8", errors="ignore")
    return "{{" in text or "{%" in text


def render_invitation_html(
    invitation: Invitation,
    invitee: Dict[str, Any],
    *,
    template_path: Optional[str] = None,
) -> str:
    """Render invitation letter HTML using default or custom Jinja2 template."""
    context = build_invitation_render_context(invitation, invitee)
    env = _get_jinja_env()

    if template_path and Path(template_path).is_file():
        source = Path(template_path).read_text(encoding="utf-8")
        template = env.from_string(source)
    else:
        template = env.get_template(DEFAULT_TEMPLATE)

    return template.render(**context)


def render_event_invitation_html(
    event,
    invitee: Dict[str, Any],
    trainers: List[Dict[str, Any]],
    *,
    template_path: Optional[str] = None,
) -> str:
    """Full formal invitation letter for a website event (same design as campaigns)."""
    context = build_event_render_context(event, invitee, trainers=trainers)
    env = _get_jinja_env()

    if (
        template_path
        and Path(template_path).is_file()
        and _is_jinja_template_file(template_path)
    ):
        source = Path(template_path).read_text(encoding="utf-8")
        template = env.from_string(source)
    else:
        template = env.get_template(DEFAULT_TEMPLATE)

    return template.render(**context)


def invitee_dict_from_model(invitee) -> Dict[str, Any]:
    return {
        "full_name": invitee.full_name,
        "email": invitee.email,
        "address": invitee.address,
        "organization": invitee.organization,
    }


def sample_invitee_dict() -> Dict[str, Any]:
    return dict(SAMPLE_INVITEE)
