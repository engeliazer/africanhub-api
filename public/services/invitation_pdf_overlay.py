"""
Post-process invitation PDFs: centered logo watermark + branded footer on every page.
"""

import logging
import os
from io import BytesIO
from typing import Dict, Optional

import requests
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

FOOTER_HEIGHT_PT = 42
FOOTER_MARGIN_X_PT = 38


def _default_logo_url() -> str:
    return (
        os.getenv("MAIL_LETTERHEAD_LOGO_URL")
        or os.getenv("MAIL_LOGO_URL")
        or "https://africanhub.ac.tz/logo.png"
    ).strip()


def _footer_enabled() -> bool:
    value = (os.getenv("MAIL_PDF_FOOTER_ENABLED") or "true").strip().lower()
    return value not in ("0", "false", "no", "off")


def _footer_show_page_numbers() -> bool:
    value = (os.getenv("MAIL_PDF_FOOTER_SHOW_PAGE_NUMBERS") or "true").strip().lower()
    return value not in ("0", "false", "no", "off")


def _default_brand() -> Dict[str, str]:
    return {
        "legal_name": (
            os.getenv("MAIL_BRAND_LEGAL_NAME")
            or "AFRICAN HUB OF BUSINESS & TECHNOLOGY"
        ).strip().upper(),
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
    }


def _fetch_logo_bytes(logo_url: str) -> Optional[bytes]:
    try:
        response = requests.get(logo_url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as exc:
        logger.warning("Failed to fetch watermark logo %s: %s", logo_url, exc)
        return None


def _logo_with_opacity(logo_bytes: bytes, opacity: float) -> bytes:
    image = Image.open(BytesIO(logo_bytes)).convert("RGBA")
    alpha = image.getchannel("A")
    image.putalpha(alpha.point(lambda value: int(value * opacity)))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _display_website(website: str) -> str:
    return website.replace("https://", "").replace("http://", "").strip("/")


def _build_watermark_layer(
    page_w: float,
    page_h: float,
    logo: bytes,
    aspect: float,
    *,
    width_ratio: float,
) -> PdfReader:
    draw_w = page_w * width_ratio
    draw_h = draw_w * aspect
    x = (page_w - draw_w) / 2
    y = (page_h - draw_h) / 2

    layer = BytesIO()
    pdf_canvas = canvas.Canvas(layer, pagesize=(page_w, page_h))
    pdf_canvas.drawImage(
        ImageReader(BytesIO(logo)),
        x,
        y,
        width=draw_w,
        height=draw_h,
        mask="auto",
        preserveAspectRatio=True,
    )
    pdf_canvas.save()
    return PdfReader(layer)


def _build_footer_layer(
    page_w: float,
    page_h: float,
    brand: Dict[str, str],
    *,
    page_num: int,
    page_count: int,
) -> PdfReader:
    navy = HexColor("#1a4b8c")
    muted = HexColor("#555555")

    layer = BytesIO()
    pdf_canvas = canvas.Canvas(layer, pagesize=(page_w, page_h))

    left = FOOTER_MARGIN_X_PT
    right = page_w - FOOTER_MARGIN_X_PT
    top = FOOTER_HEIGHT_PT

    pdf_canvas.setStrokeColor(navy)
    pdf_canvas.setLineWidth(0.6)
    pdf_canvas.line(left, top, right, top)

    pdf_canvas.setFillColor(navy)
    pdf_canvas.setFont("Helvetica-Bold", 7.5)
    pdf_canvas.drawCentredString(page_w / 2, top - 12, brand.get("legal_name", ""))

    website = _display_website(brand.get("website", ""))
    email_line = f"{brand.get('info_email', '')}  |  {website}"
    pdf_canvas.setFont("Helvetica", 6.5)
    pdf_canvas.drawCentredString(page_w / 2, top - 22, email_line)

    if _footer_show_page_numbers():
        pdf_canvas.setFillColor(muted)
        pdf_canvas.setFont("Helvetica", 6)
        pdf_canvas.drawRightString(
            right,
            top - 32,
            f"Page {page_num} of {page_count}",
        )

    pdf_canvas.save()
    return PdfReader(layer)


def apply_invitation_pdf_overlays(
    pdf_bytes: bytes,
    *,
    logo_url: Optional[str] = None,
    opacity: float = 0.2,
    width_ratio: float = 0.52,
    brand: Optional[Dict[str, str]] = None,
    footer: Optional[bool] = None,
) -> bytes:
    """
    Stamp watermark behind content and branded footer on top of every page.
    """
    if not pdf_bytes:
        return pdf_bytes

    brand_info = {**_default_brand(), **(brand or {})}
    show_footer = _footer_enabled() if footer is None else footer

    url = (logo_url or _default_logo_url()).strip()
    logo_data: Optional[tuple] = None
    if url:
        raw_logo = _fetch_logo_bytes(url)
        if raw_logo:
            try:
                logo = _logo_with_opacity(raw_logo, max(0.0, min(1.0, opacity)))
                with Image.open(BytesIO(logo)) as image:
                    img_w_px, img_h_px = image.size
                aspect = img_h_px / img_w_px if img_w_px else 1.0
                logo_data = (logo, aspect)
            except Exception as exc:
                logger.warning("Invalid watermark image: %s", exc)

    reader = PdfReader(BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    writer = PdfWriter()

    for index, page in enumerate(reader.pages, start=1):
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)

        if logo_data:
            logo, aspect = logo_data
            wm_reader = _build_watermark_layer(
                page_w,
                page_h,
                logo,
                aspect,
                width_ratio=width_ratio,
            )
            combined = wm_reader.pages[0]
            combined.merge_page(page)
        else:
            combined = page

        if show_footer:
            footer_reader = _build_footer_layer(
                page_w,
                page_h,
                brand_info,
                page_num=index,
                page_count=page_count,
            )
            combined.merge_page(footer_reader.pages[0])

        writer.add_page(combined)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def apply_logo_watermark(
    pdf_bytes: bytes,
    logo_url: Optional[str] = None,
    *,
    opacity: float = 0.2,
    width_ratio: float = 0.52,
) -> bytes:
    """Backward-compatible watermark-only helper."""
    return apply_invitation_pdf_overlays(
        pdf_bytes,
        logo_url=logo_url,
        opacity=opacity,
        width_ratio=width_ratio,
        footer=False,
    )
