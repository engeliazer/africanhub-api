"""
Apply a centered logo watermark to every page of an invitation PDF (behind text).
"""

import logging
import os
from io import BytesIO
from typing import Optional

import requests
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


def _default_logo_url() -> str:
    return (
        os.getenv("MAIL_LETTERHEAD_LOGO_URL")
        or os.getenv("MAIL_LOGO_URL")
        or "https://africanhub.ac.tz/logo.png"
    ).strip()


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


def apply_logo_watermark(
    pdf_bytes: bytes,
    logo_url: Optional[str] = None,
    *,
    opacity: float = 0.5,
    width_ratio: float = 0.52,
) -> bytes:
    """
    Stamp a centered semi-transparent logo on every page, behind existing content.
    """
    if not pdf_bytes:
        return pdf_bytes

    url = (logo_url or _default_logo_url()).strip()
    if not url:
        return pdf_bytes

    raw_logo = _fetch_logo_bytes(url)
    if not raw_logo:
        return pdf_bytes

    try:
        logo = _logo_with_opacity(raw_logo, max(0.0, min(1.0, opacity)))
        with Image.open(BytesIO(logo)) as image:
            img_w_px, img_h_px = image.size
        aspect = img_h_px / img_w_px if img_w_px else 1.0
    except Exception as exc:
        logger.warning("Invalid watermark image: %s", exc)
        return pdf_bytes

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)
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

        watermark_page = PdfReader(layer).pages[0]
        watermark_page.merge_page(page)
        writer.add_page(watermark_page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
