"""
Jinja2 HTML generation for full invitation campaigns (7 sections).
"""

import html
import os
from datetime import date, time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from applications.models.models import Invitation, InvitationTrainer

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

        def nl2br(value) -> str:
            if value is None:
                return ""
            text = html.escape(str(value))
            return text.replace("\n", "<br />")

        env.filters["nl2br"] = nl2br
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


def _brand_context(invitation: Invitation) -> Dict[str, str]:
    return {
        "name": (os.getenv("MAIL_FROM_NAME") or "The African Hub").strip().upper(),
        "tagline": (
            os.getenv("MAIL_BRAND_TAGLINE") or "Building Accounting Skills for the Real World"
        ).strip(),
        "logo_url": (os.getenv("MAIL_LOGO_URL") or "").strip(),
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

    return {
        "brand": _brand_context(invitation),
        "invitation": {
            "title": invitation.title,
            "email_message": invitation.email_message,
            "email_subject": invitation.email_subject,
        },
        "invitee": {
            "full_name": invitee.get("full_name") or "",
            "email": invitee.get("email") or "",
            "address": invitee.get("address") or "",
            "organization": invitee.get("organization") or "",
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
