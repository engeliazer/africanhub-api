"""
Convert rendered invitation HTML to PDF for campaign preview and sending.
"""

import logging
import re
from io import BytesIO
from typing import Tuple

from applications.models.models import Invitation

from public.services.invitation_html_service import (
    _brand_context,
    _watermark_opacity,
    invitee_dict_from_model,
    render_invitation_html,
    sample_invitee_dict,
)
from public.services.invitation_pdf_overlay import apply_invitation_pdf_overlays

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
        raise RuntimeError(
            "xhtml2pdf is not installed in this Python environment. "
            "On the server run: source venv/bin/activate && pip install -r requirements.txt "
            "then restart Gunicorn and Celery. "
            "Verify with: python scripts/check_invitation_pdf_deps.py"
        ) from e

    buffer = BytesIO()
    status = pisa.CreatePDF(html_content, dest=buffer, encoding="utf-8")
    if status.err:
        raise RuntimeError("Failed to generate invitation PDF")

    brand = _brand_context(invitation)
    pdf_bytes = apply_invitation_pdf_overlays(
        buffer.getvalue(),
        opacity=_watermark_opacity(),
        brand={
            "legal_name": brand["legal_name"],
            "info_email": brand["info_email"],
            "website": brand["website"],
        },
    )

    filename = invitation_pdf_filename(invitee.get("full_name") or "")
    logger.info(
        "Generated invitation PDF %s for invitation %s",
        filename,
        invitation.id,
    )
    return pdf_bytes, filename


def render_invitation_pdf_for_invitee(invitation: Invitation, invitee_model) -> Tuple[bytes, str]:
    return render_invitation_pdf_bytes(invitation, invitee_dict_from_model(invitee_model))


def render_sample_invitation_pdf(invitation: Invitation) -> Tuple[bytes, str]:
    return render_invitation_pdf_bytes(invitation, sample_invitee_dict())
