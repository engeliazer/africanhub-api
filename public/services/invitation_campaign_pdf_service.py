"""
Convert rendered invitation HTML to PDF for campaign preview and sending.
"""

import logging
import re
from io import BytesIO
from typing import Tuple

from applications.models.models import Invitation

from public.services.invitation_html_service import (
    invitee_dict_from_model,
    render_invitation_html,
    sample_invitee_dict,
)

logger = logging.getLogger(__name__)


def invitation_pdf_filename(full_name: str) -> str:
    """File naming per spec: Invitation_John_Doe.pdf"""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", (full_name or "Invitee").strip()).strip("_")
    safe = safe[:60] or "Invitee"
    return f"Invitation_{safe}.pdf"


def render_invitation_pdf_bytes(
    invitation: Invitation,
    invitee: dict,
) -> Tuple[bytes, str]:
    """
    Render invitation HTML to PDF bytes.

    Returns (pdf_bytes, download_filename).
    """
    html_content = render_invitation_html(
        invitation,
        invitee,
        template_path=invitation.invitation_template_path,
    )

    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError("xhtml2pdf is not installed") from e

    buffer = BytesIO()
    status = pisa.CreatePDF(html_content, dest=buffer, encoding="utf-8")
    if status.err:
        raise RuntimeError("Failed to generate invitation PDF")

    filename = invitation_pdf_filename(invitee.get("full_name") or "")
    logger.info(
        "Generated invitation PDF %s for invitation %s",
        filename,
        invitation.id,
    )
    return buffer.getvalue(), filename


def render_invitation_pdf_for_invitee(invitation: Invitation, invitee_model) -> Tuple[bytes, str]:
    return render_invitation_pdf_bytes(invitation, invitee_dict_from_model(invitee_model))


def render_sample_invitation_pdf(invitation: Invitation) -> Tuple[bytes, str]:
    return render_invitation_pdf_bytes(invitation, sample_invitee_dict())
