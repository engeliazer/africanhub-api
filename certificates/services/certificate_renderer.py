"""
Render certificate PDFs: empty background + coordinate overlay (ReportLab + pypdf).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from certificates.services.storage_path_utils import read_storage_asset_bytes

logger = logging.getLogger(__name__)

A4_WIDTH = 595.28
A4_HEIGHT = 841.89

# ~150 DPI for A4 — enough for print preview without multi‑MB PDFs.
MAX_BACKGROUND_WIDTH_PX = 1240
MAX_BACKGROUND_HEIGHT_PX = 1754
BACKGROUND_JPEG_QUALITY = 85
LOGO_JPEG_QUALITY = 80

# Do not embed full PDFs in JSON responses above this size (raw bytes).
MAX_JSON_INLINE_PDF_BYTES = 2 * 1024 * 1024

DEFAULT_FIELD_LAYOUT: Dict[str, Any] = {
    "page": {"width": A4_WIDTH, "height": A4_HEIGHT},
    "certificate_title": {
        "x": 297.64,
        "y": 720,
        "font": "Helvetica-Bold",
        "size": 22,
        "align": "center",
    },
    "home_logo": {"x": 70, "y": 770, "max_width": 110, "max_height": 55},
    "invited_logo": {"x": 415, "y": 770, "max_width": 110, "max_height": 55},
    "participant_name": {
        "x": 297.64,
        "y": 585,
        "font": "Helvetica-Bold",
        "size": 18,
        "align": "center",
    },
    "participation_line": {
        "x": 297.64,
        "y": 535,
        "font": "Helvetica",
        "size": 12,
        "align": "center",
        "max_width": 470,
    },
    "subject_title": {
        "x": 297.64,
        "y": 505,
        "font": "Helvetica-Bold",
        "size": 13,
        "align": "center",
        "max_width": 470,
    },
    "venue_line": {
        "x": 297.64,
        "y": 465,
        "font": "Helvetica",
        "size": 11,
        "align": "center",
        "max_width": 470,
    },
    "date_line": {
        "x": 297.64,
        "y": 435,
        "font": "Helvetica",
        "size": 11,
        "align": "center",
        "max_width": 470,
    },
    "cpd_line": {
        "x": 297.64,
        "y": 405,
        "font": "Helvetica",
        "size": 11,
        "align": "center",
        "max_width": 470,
        "optional": True,
    },
    "cert_number": {
        "x": 520,
        "y": 78,
        "font": "Helvetica",
        "size": 10,
        "align": "right",
    },
    "signatory_1": {
        "name_x": 150,
        "name_y": 145,
        "title_y": 128,
        "signature_x": 150,
        "signature_y": 175,
        "signature_width": 110,
        "signature_height": 42,
        "font": "Helvetica",
        "size": 10,
        "align": "center",
    },
    "signatory_2": {
        "name_x": 445,
        "name_y": 145,
        "title_y": 128,
        "signature_x": 445,
        "signature_y": 175,
        "signature_width": 110,
        "signature_height": 42,
        "font": "Helvetica",
        "size": 10,
        "align": "center",
    },
}


class CertificateRenderer:
    def __init__(self, render_data: Dict[str, Any]):
        self.data = render_data
        template = render_data["template"]
        self.layout = template.get("field_layout") or DEFAULT_FIELD_LAYOUT
        page = self.layout.get("page") or {}
        self.page_w = float(page.get("width") or A4_WIDTH)
        self.page_h = float(page.get("height") or A4_HEIGHT)

    def render_pdf_bytes(self) -> bytes:
        background_bytes = self._load_background()
        overlay_bytes = self._build_overlay_layer()
        return self._merge_layers(background_bytes, overlay_bytes)

    @staticmethod
    def _optimize_raster_image(
        image_bytes: bytes,
        *,
        max_width_px: int = MAX_BACKGROUND_WIDTH_PX,
        max_height_px: int = MAX_BACKGROUND_HEIGHT_PX,
        jpeg_quality: int = BACKGROUND_JPEG_QUALITY,
    ) -> bytes:
        """Downscale and JPEG-compress raster assets before embedding in PDF."""
        with Image.open(BytesIO(image_bytes)) as image:
            if image.mode == "P":
                image = image.convert("RGBA")
            if image.mode in ("RGBA", "LA"):
                flattened = Image.new("RGB", image.size, (255, 255, 255))
                flattened.paste(image, mask=image.split()[-1])
                image = flattened
            else:
                image = image.convert("RGB")

            image.thumbnail((max_width_px, max_height_px), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
            return buffer.getvalue()

    def _read_background_bytes(self) -> bytes:
        background_url = self.data["template"]["background_url"]
        raw, error = read_storage_asset_bytes(background_url)
        if error:
            raise ValueError(error)
        return raw

    def _load_background(self) -> bytes:
        raw = self._read_background_bytes()
        if raw[:4] == b"%PDF":
            if len(raw) > 3_000_000:
                logger.warning(
                    "Large PDF background (%s bytes); upload a JPEG/PNG template or "
                    "a compressed PDF for smaller certificate output",
                    len(raw),
                )
            return raw
        return self._image_bytes_to_pdf_page(raw)

    def _image_bytes_to_pdf_page(self, image_bytes: bytes) -> bytes:
        optimized = self._optimize_raster_image(image_bytes)
        buffer = BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=(self.page_w, self.page_h))
        image_reader = ImageReader(BytesIO(optimized))
        img_w, img_h = image_reader.getSize()
        aspect = img_h / float(img_w) if img_w else 1.0
        draw_w = self.page_w
        draw_h = draw_w * aspect
        if draw_h > self.page_h:
            draw_h = self.page_h
            draw_w = draw_h / aspect if aspect else self.page_w
        x = (self.page_w - draw_w) / 2
        y = (self.page_h - draw_h) / 2
        pdf_canvas.drawImage(
            image_reader,
            x,
            y,
            width=draw_w,
            height=draw_h,
            mask=None,
        )
        pdf_canvas.save()
        return buffer.getvalue()

    def _build_overlay_layer(self) -> bytes:
        buffer = BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=(self.page_w, self.page_h))

        if self.data.get("show_home_logo"):
            self._draw_logo(pdf_canvas, self.data.get("home_logo_url"), "home_logo")
        if self.data.get("show_invited_logo"):
            self._draw_logo(pdf_canvas, self.data.get("invited_logo_url"), "invited_logo")

        self._draw_text(pdf_canvas, self.data["certificate_title"], "certificate_title")
        self._draw_text(pdf_canvas, self.data["participant_name"], "participant_name")
        self._draw_wrapped_text(pdf_canvas, self.data["participation_line"], "participation_line")
        self._draw_wrapped_text(pdf_canvas, self.data["subject_title"], "subject_title")
        self._draw_wrapped_text(pdf_canvas, self.data["venue_line"], "venue_line")
        self._draw_wrapped_text(pdf_canvas, self.data["date_line"], "date_line")

        if self.data.get("qualifies_for_cpd") and self.data.get("cpd_line"):
            self._draw_wrapped_text(pdf_canvas, self.data["cpd_line"], "cpd_line")

        self._draw_text(pdf_canvas, self.data["cert_number"], "cert_number")

        for index, signatory in enumerate(self.data.get("signatories") or [], start=1):
            self._draw_signatory(pdf_canvas, signatory, f"signatory_{index}")

        if self.data.get("preview"):
            self._draw_preview_watermark(pdf_canvas)

        pdf_canvas.save()
        return buffer.getvalue()

    def _draw_preview_watermark(self, pdf_canvas) -> None:
        pdf_canvas.saveState()
        pdf_canvas.setFont("Helvetica-Bold", 72)
        pdf_canvas.setFillGray(0.85)
        if hasattr(pdf_canvas, "setFillAlpha"):
            pdf_canvas.setFillAlpha(0.25)
        pdf_canvas.translate(self.page_w / 2, self.page_h / 2)
        pdf_canvas.rotate(45)
        pdf_canvas.drawCentredString(0, 0, "PREVIEW")
        pdf_canvas.restoreState()

    def _layout_for(self, key: str) -> Dict[str, Any]:
        return dict(self.layout.get(key) or DEFAULT_FIELD_LAYOUT.get(key) or {})

    def _draw_text(self, pdf_canvas, text: str, layout_key: str) -> None:
        if not text:
            return
        layout = self._layout_for(layout_key)
        font = layout.get("font", "Helvetica")
        size = float(layout.get("size", 12))
        x = float(layout.get("x", 0))
        y = float(layout.get("y", 0))
        align = layout.get("align", "left")

        pdf_canvas.setFont(font, size)
        if align == "center":
            pdf_canvas.drawCentredString(x, y, text)
        elif align == "right":
            pdf_canvas.drawRightString(x, y, text)
        else:
            pdf_canvas.drawString(x, y, text)

    def _wrap_text(self, text: str, font: str, size: float, max_width: float) -> List[str]:
        words = (text or "").split()
        if not words:
            return []

        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdf_string_width(candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _draw_wrapped_text(self, pdf_canvas, text: str, layout_key: str) -> None:
        if not text:
            return
        layout = self._layout_for(layout_key)
        font = layout.get("font", "Helvetica")
        size = float(layout.get("size", 12))
        x = float(layout.get("x", 0))
        y = float(layout.get("y", 0))
        align = layout.get("align", "left")
        max_width = float(layout.get("max_width", self.page_w - 80))
        line_height = float(layout.get("line_height", size * 1.25))

        lines = self._wrap_text(text, font, size, max_width)
        pdf_canvas.setFont(font, size)
        cursor_y = y
        for line in lines:
            if align == "center":
                pdf_canvas.drawCentredString(x, cursor_y, line)
            elif align == "right":
                pdf_canvas.drawRightString(x, cursor_y, line)
            else:
                pdf_canvas.drawString(x, cursor_y, line)
            cursor_y -= line_height

    def _draw_logo(self, pdf_canvas, logo_url: Optional[str], layout_key: str) -> None:
        image_bytes = self._load_image_bytes(logo_url)
        if not image_bytes:
            return

        layout = self._layout_for(layout_key)
        x = float(layout.get("x", 0))
        y = float(layout.get("y", 0))
        max_width = float(layout.get("max_width", 100))
        max_height = float(layout.get("max_height", 50))

        max_logo_px = max(int(max_width * 3), 120)
        optimized = self._optimize_raster_image(
            image_bytes,
            max_width_px=max_logo_px,
            max_height_px=max_logo_px,
            jpeg_quality=LOGO_JPEG_QUALITY,
        )

        with Image.open(BytesIO(optimized)) as image:
            width_px, height_px = image.size
        aspect = height_px / width_px if width_px else 1.0
        draw_w = max_width
        draw_h = draw_w * aspect
        if draw_h > max_height:
            draw_h = max_height
            draw_w = draw_h / aspect if aspect else max_width

        pdf_canvas.drawImage(
            ImageReader(BytesIO(optimized)),
            x,
            y - draw_h,
            width=draw_w,
            height=draw_h,
            mask=None,
            preserveAspectRatio=True,
        )

    def _draw_signatory(self, pdf_canvas, signatory: Dict[str, Any], layout_key: str) -> None:
        layout = self._layout_for(layout_key)
        font = layout.get("font", "Helvetica")
        size = float(layout.get("size", 10))
        align = layout.get("align", "center")

        signature_bytes = self._load_image_bytes(signatory.get("signature_url"))
        if signature_bytes:
            sig_x = float(layout.get("signature_x", layout.get("name_x", 0)))
            sig_y = float(layout.get("signature_y", layout.get("name_y", 0)))
            sig_w = float(layout.get("signature_width", 100))
            sig_h = float(layout.get("signature_height", 40))
            optimized_sig = self._optimize_raster_image(
                signature_bytes,
                max_width_px=int(sig_w * 3),
                max_height_px=int(sig_h * 3),
                jpeg_quality=LOGO_JPEG_QUALITY,
            )
            pdf_canvas.drawImage(
                ImageReader(BytesIO(optimized_sig)),
                sig_x - (sig_w / 2 if align == "center" else 0),
                sig_y,
                width=sig_w,
                height=sig_h,
                mask=None,
                preserveAspectRatio=True,
            )

        pdf_canvas.setFont(font, size)
        name_x = float(layout.get("name_x", 0))
        name_y = float(layout.get("name_y", 0))
        title_y = float(layout.get("title_y", name_y - 14))
        full_name = signatory.get("full_name") or ""
        title = signatory.get("title") or ""

        if align == "center":
            pdf_canvas.drawCentredString(name_x, name_y, full_name)
            pdf_canvas.drawCentredString(name_x, title_y, title)
        elif align == "right":
            pdf_canvas.drawRightString(name_x, name_y, full_name)
            pdf_canvas.drawRightString(name_x, title_y, title)
        else:
            pdf_canvas.drawString(name_x, name_y, full_name)
            pdf_canvas.drawString(name_x, title_y, title)

    def _load_image_bytes(self, url: Optional[str]) -> Optional[bytes]:
        if not url:
            return None
        raw, error = read_storage_asset_bytes(url)
        if error:
            logger.warning("Failed to load image %s: %s", url, error)
            return None
        return raw

    def _merge_layers(self, background_bytes: bytes, overlay_bytes: bytes) -> bytes:
        try:
            background_reader = PdfReader(BytesIO(background_bytes))
            overlay_reader = PdfReader(BytesIO(overlay_bytes))
        except Exception as exc:
            raise ValueError(f"Invalid certificate background PDF: {exc}") from exc

        if not background_reader.pages:
            raise ValueError("Certificate background PDF has no pages")

        writer = PdfWriter()
        background_page = background_reader.pages[0]
        overlay_page = overlay_reader.pages[0]
        background_page.merge_page(overlay_page)
        writer.add_page(background_page)
        CertificateRenderer._compress_writer_pages(writer)

        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    @staticmethod
    def _compress_writer_pages(writer: PdfWriter) -> None:
        """Compress page streams after they are attached to the writer (pypdf requirement)."""
        for page in writer.pages:
            try:
                page.compress_content_streams()
            except Exception as exc:
                logger.warning("PDF stream compression skipped: %s", exc)


def pdf_string_width(text: str, font: str, size: float) -> float:
    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=(A4_WIDTH, A4_HEIGHT))
    pdf_canvas.setFont(font, size)
    return pdf_canvas.stringWidth(text, font, size)


def format_cert_number(
    pattern: str,
    *,
    home_code: str,
    invited_code: Optional[str],
    start_date: date,
    training_id: int,
    sequence: int,
    preview: bool = False,
) -> str:
    if preview:
        return "PREVIEW"

    replacements = {
        "{home_code}": home_code or "",
        "{invited_code}": invited_code or home_code or "",
        "{mm}": f"{start_date.month:02d}",
        "{yy}": f"{start_date.year % 100:02d}",
        "{yyyy}": str(start_date.year),
        "{seq}": f"{sequence:05d}",
        "{training_id}": str(training_id),
    }

    result = pattern
    for token, value in replacements.items():
        result = result.replace(token, value)

    if re.search(r"\{[^}]+\}", result):
        result = re.sub(r"\{[^}]+\}", "", result)
        result = re.sub(r"/{2,}", "/", result).strip("/")

    return result


def format_display_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")
