"""
Jinja2 HTML generation for full invitation campaigns (7 sections).
"""

import html
import os
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from applications.models.models import Invitation, InvitationTrainer
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

        def nl2br(value) -> str:
            text = html.escape(_normalize_line_breaks(value))
            return text.replace("\n", "<br />")

        def richtext(value) -> Markup:
            """Paragraphs + line breaks; safe for invitee-personalized message HTML."""
            text = html.escape(_normalize_line_breaks(value).strip())
            if not text:
                return Markup("")
            paragraphs = re.split(r"\n\s*\n", text)
            blocks = [
                f'<p style="margin:0 0 12px 0;text-align:justify;">'
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


def _brand_context(invitation: Invitation) -> Dict[str, str]:
    logo = (os.getenv("MAIL_LOGO_URL") or "https://africanhub.ac.tz/logo.png").strip()
    letterhead_logo = (os.getenv("MAIL_LETTERHEAD_LOGO_URL") or logo).strip()
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
            or invitation.source_email
            or "trainings@africanhub.ac.tz"
        ).strip(),
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
    start_date = _format_date(invitation.start_date)
    end_date = _format_date(invitation.end_date)
    if start_date and end_date and start_date != end_date:
        date_range = f"{start_date} – {end_date}"
    else:
        date_range = start_date or end_date or ""

    start_time = _format_time(invitation.start_time)
    end_time = _format_time(invitation.end_time)
    if start_time and end_time:
        time_range = f"{start_time} – {end_time}"
    else:
        time_range = start_time or end_time or ""

    course_fee = _format_money(invitation.course_fee)
    deposit_amount = _format_money(invitation.deposit_amount)
    has_payment = any([
        course_fee,
        deposit_amount,
        invitation.reservation_deadline,
        invitation.bank_name,
        invitation.bank_account_name,
        invitation.bank_account_number,
    ])

    letter_date = _format_letter_date()
    full_name = invitee.get("full_name") or ""
    organization, address_line = _invitee_addressee_parts(invitee)
    return {
        "brand": _brand_context(invitation),
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
        "course": {
            "title": invitation.course_title,
            "description": invitation.course_description,
            "venue": invitation.venue,
            "start_date": start_date,
            "end_date": end_date,
            "date_range": date_range,
            "start_time": start_time,
            "end_time": end_time,
            "time_range": time_range,
            "learning_outcomes": _learning_outcomes_list(invitation.learning_outcomes),
        },
        "trainers": trainers if trainers is not None else _trainers_from_invitation(invitation),
        "payment": {
            "course_fee": course_fee,
            "deposit_amount": deposit_amount,
            "reservation_deadline": _format_date(invitation.reservation_deadline),
            "bank_account_name": invitation.bank_account_name,
            "bank_account_number": invitation.bank_account_number,
            "bank_name": invitation.bank_name,
            "has_payment_info": has_payment,
        },
    }


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


def invitee_dict_from_model(invitee) -> Dict[str, Any]:
    return {
        "full_name": invitee.full_name,
        "email": invitee.email,
        "address": invitee.address,
        "organization": invitee.organization,
    }


def sample_invitee_dict() -> Dict[str, Any]:
    return dict(SAMPLE_INVITEE)
