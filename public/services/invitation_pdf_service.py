"""
Generate personalized invitation PDFs from HTML templates.
"""

import html
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

from public.services.invitation_template_service import read_template_html

logger = logging.getLogger(__name__)

NAME = "[NAME]"
ADDRESS = "[ADDRESS]"
ORGANIZATION = "[ORGANIZATION]"


def default_invitation_template_html() -> str:
    """Built-in African Hub invitation letter (used when no custom template uploaded)."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <style>
    @page { size: A4; margin: 2cm; }
    body {
      font-family: Helvetica, Arial, sans-serif;
      color: #1F2937;
      font-size: 12pt;
      line-height: 1.6;
    }
    .header-bar {
      height: 6px;
      background: linear-gradient(90deg, #A8861E, #C9A227);
      margin-bottom: 24px;
    }
    .brand {
      font-size: 18pt;
      font-weight: bold;
      letter-spacing: 0.05em;
      color: #1F2937;
      margin: 0 0 4px 0;
    }
    .tagline {
      font-size: 10pt;
      color: #6B7280;
      margin: 0 0 28px 0;
    }
    .invitee-box {
      border: 1px solid #E5E7EB;
      border-left: 4px solid #C9A227;
      padding: 16px 20px;
      margin: 24px 0;
      background: #FAFAFA;
    }
    .invitee-label {
      font-size: 9pt;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #6B7280;
      margin: 0 0 4px 0;
    }
    .invitee-value {
      font-size: 12pt;
      font-weight: bold;
      margin: 0 0 12px 0;
      color: #1F2937;
    }
    .body-text { margin: 20px 0; }
    .signature { margin-top: 40px; }
    .gold { color: #A8861E; }
  </style>
</head>
<body>
  <div class="header-bar"></div>
  <p class="brand">THE AFRICAN HUB</p>
  <p class="tagline">Building Accounting Skills for the Real World</p>

  <div class="invitee-box">
    <p class="invitee-label">Invitee</p>
    <p class="invitee-value">[NAME]</p>
    <p class="invitee-label">Organization</p>
    <p class="invitee-value">[ORGANIZATION]</p>
    <p class="invitee-label">Address</p>
    <p class="invitee-value">[ADDRESS]</p>
  </div>

  <div class="body-text">
    <p>Dear <strong>[NAME]</strong>,</p>
    <p>
      On behalf of <span class="gold">The African Hub</span>, we are delighted to extend
      this invitation to you and <strong>[ORGANIZATION]</strong>.
    </p>
    <p>
      We look forward to your participation. Please find your personalized invitation
      details above. Should you have any questions, reply to this email and our team
      will be glad to assist.
    </p>
    <p>We hope to see you there.</p>
  </div>

  <div class="signature">
    <p>Warm regards,</p>
    <p><strong>The African Hub Team</strong><br />
    trainings@africanhub.ac.tz</p>
  </div>
</body>
</html>"""


def personalize_invitation_template(
    template_html: str,
    *,
    full_name: str,
    address: str,
    organization: str,
) -> str:
    """Replace placeholders. Values are HTML-escaped for safe PDF rendering."""
    safe_name = html.escape(full_name or "")
    safe_address = html.escape(address or "").replace("\n", "<br />")
    safe_org = html.escape(organization or "")
    return (
        template_html.replace(NAME, safe_name)
        .replace(ADDRESS, safe_address)
        .replace(ORGANIZATION, safe_org)
    )


def generate_invitation_pdf(
    *,
    template_path: Optional[str],
    full_name: str,
    address: str,
    organization: str,
    batch_id: int,
    recipient_id: int,
) -> Tuple[str, str]:
    """
    Render personalized invitation HTML to a temporary PDF file.

    Returns:
        (absolute_pdf_path, download_filename)
    """
    template_html = read_template_html(template_path)
    rendered = personalize_invitation_template(
        template_html,
        full_name=full_name,
        address=address,
        organization=organization,
    )

    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError("xhtml2pdf is not installed") from e

    out_dir = Path(tempfile.gettempdir()) / "invitation_pdfs" / str(batch_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in full_name)[:40]
    filename = f"Invitation_{safe_name}_{recipient_id}.pdf"
    pdf_path = out_dir / f"{uuid.uuid4().hex}_{filename}"

    with open(pdf_path, "wb") as pdf_file:
        status = pisa.CreatePDF(rendered, dest=pdf_file, encoding="utf-8")
    if status.err:
        if pdf_path.is_file():
            pdf_path.unlink()
        raise RuntimeError("Failed to generate invitation PDF")

    logger.info("Generated invitation PDF %s for recipient %s", pdf_path, recipient_id)
    return str(pdf_path), filename


def delete_temp_pdf(pdf_path: Optional[str]) -> None:
    if not pdf_path:
        return
    path = Path(pdf_path)
    if path.is_file():
        path.unlink(missing_ok=True)
