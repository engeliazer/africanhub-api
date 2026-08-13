"""
Render certificate PDFs: empty background + coordinate overlay (ReportLab + pypdf).
Typography and layout follow the AHBT sample certificate.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from certificates.services.certificate_fonts import (
    SERIF,
    SERIF_BOLD,
    ensure_certificate_fonts,
    participant_name_font,
)
from certificates.services.certificate_styles import (
    A4_HEIGHT,
    A4_WIDTH,
    COLOR_FLOURISH,
    DEFAULT_CERTIFICATE_HEADING,
    DEFAULT_CERTIFICATE_SUBHEADING,
    DEFAULT_CERT_INTRO,
    DEFAULT_FIELD_LAYOUT,
)
from certificates.services.storage_path_utils import read_storage_asset_bytes

logger = logging.getLogger(__name__)

# ~150 DPI for A4 — enough for print preview without multi‑MB PDFs.
MAX_BACKGROUND_WIDTH_PX = 1240
MAX_BACKGROUND_HEIGHT_PX = 1754
BACKGROUND_JPEG_QUALITY = 85
LOGO_JPEG_QUALITY = 80

# Do not embed full PDFs in JSON responses above this size (raw bytes).
MAX_JSON_INLINE_PDF_BYTES = 2 * 1024 * 1024


class CertificateRenderer:
    def __init__(self, render_data: Dict[str, Any]):
        ensure_certificate_fonts()
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

    @staticmethod
    def _optimize_background_image(image_bytes: bytes) -> bytes:
        """Resize background rasters; keep PNG to preserve faint watermark patterns."""
        with Image.open(BytesIO(image_bytes)) as image:
            if image.mode == "P":
                image = image.convert("RGBA")
            if image.mode in ("RGBA", "LA"):
                flattened = Image.new("RGB", image.size, (255, 255, 255))
                flattened.paste(image, mask=image.split()[-1])
                image = flattened
            else:
                image = image.convert("RGB")

            image.thumbnail(
                (MAX_BACKGROUND_WIDTH_PX, MAX_BACKGROUND_HEIGHT_PX),
                Image.Resampling.LANCZOS,
            )
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()

    @staticmethod
    def _prepare_watermark_png(image_bytes: bytes, opacity: float) -> bytes:
        """Apply opacity; key out white JPEG backgrounds so tiles stay visible."""
        with Image.open(BytesIO(image_bytes)) as image:
            image = image.convert("RGBA")
            pixels = list(image.getdata())
            adjusted = []
            for r, g, b, a in pixels:
                if a == 0:
                    adjusted.append((r, g, b, 0))
                    continue
                if r >= 235 and g >= 235 and b >= 235:
                    adjusted.append((255, 255, 255, 0))
                else:
                    adjusted.append((r, g, b, int(a * opacity)))
            image.putdata(adjusted)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

    def _draw_template_watermark(self, pdf_canvas) -> None:
        if not self.data.get("watermark_enabled"):
            return
        watermark_url = self.data.get("watermark_logo_url")
        image_bytes = self._load_image_bytes(watermark_url)
        if not image_bytes:
            logger.warning(
                "Certificate watermark enabled but logo could not be loaded: %s",
                watermark_url,
            )
            return

        opacity = float(self.data.get("watermark_opacity") or 0.12)
        style = (self.data.get("watermark_style") or "distributed").strip().lower()
        layout = self._layout_for("watermark")
        watermark_png = self._prepare_watermark_png(image_bytes, opacity)

        reader = ImageReader(BytesIO(watermark_png))
        src_w, src_h = reader.getSize()
        aspect = src_h / float(src_w) if src_w else 1.0

        pdf_canvas.saveState()

        if style == "center":
            draw_w = float(layout.get("center_width", 260))
            draw_h = draw_w * aspect
            x = (self.page_w - draw_w) / 2
            y = (self.page_h - draw_h) / 2
            pdf_canvas.drawImage(reader, x, y, width=draw_w, height=draw_h, mask="auto")
        else:
            tile_w = float(layout.get("tile_width", 110))
            tile_h = tile_w * aspect
            gap_x = float(layout.get("gap_x", 28))
            gap_y = float(layout.get("gap_y", 36))
            margin = float(layout.get("margin", 40))
            y = margin
            while y < self.page_h - margin:
                x = margin
                while x < self.page_w - margin:
                    pdf_canvas.drawImage(reader, x, y, width=tile_w, height=tile_h, mask="auto")
                    x += tile_w + gap_x
                y += tile_h + gap_y

        pdf_canvas.restoreState()

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
        optimized = self._optimize_background_image(image_bytes)
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
        pdf_canvas.drawImage(image_reader, x, y, width=draw_w, height=draw_h, mask=None)
        pdf_canvas.save()
        return buffer.getvalue()

    def _build_overlay_layer(self) -> bytes:
        buffer = BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=(self.page_w, self.page_h))

        self._draw_template_watermark(pdf_canvas)

        if self.data.get("show_home_logo"):
            self._draw_logo(pdf_canvas, self.data.get("home_logo_url"), "home_logo")
        if self.data.get("show_invited_logo"):
            self._draw_logo(pdf_canvas, self.data.get("invited_logo_url"), "invited_logo")

        self._draw_text(pdf_canvas, self.data.get("cert_number"), "cert_number")
        self._draw_text(pdf_canvas, self.data.get("certificate_heading"), "certificate_heading")
        self._draw_subheading_with_flourishes(pdf_canvas)
        self._draw_text(pdf_canvas, self.data.get("cert_intro"), "cert_intro")
        self._draw_participant_name(pdf_canvas, self.data.get("participant_name"))
        self._draw_wrapped_text(pdf_canvas, self.data.get("participation_line"), "participation_line")
        self._draw_wrapped_text(pdf_canvas, self.data.get("subject_title"), "subject_title")
        self._draw_wrapped_text(pdf_canvas, self.data.get("venue_line"), "venue_line")
        self._draw_wrapped_text(pdf_canvas, self.data.get("date_line"), "date_line")

        if self.data.get("qualifies_for_cpd") and self.data.get("cpd_line"):
            self._draw_wrapped_text(pdf_canvas, self.data.get("cpd_line"), "cpd_line")

        signatories = self.data.get("signatories") or []
        for index, signatory in enumerate(signatories, start=1):
            self._draw_signatory(pdf_canvas, signatory, f"signatory_{index}")
        if len(signatories) >= 2:
            self._draw_center_signatory_flourish(pdf_canvas)

        if self.data.get("preview"):
            self._draw_preview_watermark(pdf_canvas)

        pdf_canvas.save()
        return buffer.getvalue()

    def _draw_subheading_with_flourishes(self, pdf_canvas) -> None:
        text = self.data.get("certificate_subheading") or DEFAULT_CERTIFICATE_SUBHEADING
        layout = self._layout_for("certificate_subheading")
        self._draw_text(pdf_canvas, text, "certificate_subheading")
        if layout.get("draw_flourishes", True):
            self._draw_side_flourishes(
                pdf_canvas,
                float(layout.get("x", self.page_w / 2)),
                float(layout.get("y", 662)),
                layout.get("color", COLOR_FLOURISH),
            )

    def _draw_side_flourishes(self, pdf_canvas, center_x: float, y: float, color: str) -> None:
        pdf_canvas.saveState()
        pdf_canvas.setStrokeColor(HexColor(color))
        pdf_canvas.setFillColor(HexColor(color))
        pdf_canvas.setLineWidth(0.8)
        for side in (-1, 1):
            ox = center_x + side * 118
            path = pdf_canvas.beginPath()
            path.moveTo(ox, y + 2)
            path.curveTo(ox + side * 18, y + 10, ox + side * 22, y - 6, ox + side * 8, y - 8)
            path.curveTo(ox + side * 2, y - 10, ox - side * 6, y + 2, ox, y + 2)
            pdf_canvas.drawPath(path, stroke=1, fill=0)
        pdf_canvas.restoreState()

    def _draw_center_signatory_flourish(self, pdf_canvas) -> None:
        layout = self._layout_for("signatory_center_flourish")
        cx = float(layout.get("x", self.page_w / 2))
        cy = float(layout.get("y", 138))
        color = layout.get("color", COLOR_FLOURISH)
        pdf_canvas.saveState()
        pdf_canvas.setStrokeColor(HexColor(color))
        pdf_canvas.setLineWidth(0.9)
        pdf_canvas.circle(cx, cy, 5, stroke=1, fill=0)
        pdf_canvas.line(cx - 9, cy, cx + 9, cy)
        pdf_canvas.line(cx, cy - 9, cx, cy + 9)
        pdf_canvas.restoreState()

    def _draw_participant_name(self, pdf_canvas, text: Optional[str]) -> None:
        if not text:
            return
        layout = self._layout_for("participant_name")
        font = participant_name_font()
        size = float(layout.get("size", 34))
        x = float(layout.get("x", self.page_w / 2))
        y = float(layout.get("y", 592))
        align = layout.get("align", "center")
        color = layout.get("color", "#1A1A1A")

        pdf_canvas.setFillColor(HexColor(color))
        pdf_canvas.setFont(font, size)
        if align == "center":
            pdf_canvas.drawCentredString(x, y, text)
            text_width = pdf_string_width(text, font, size)
        elif align == "right":
            pdf_canvas.drawRightString(x, y, text)
            text_width = pdf_string_width(text, font, size)
        else:
            pdf_canvas.drawString(x, y, text)
            text_width = pdf_string_width(text, font, size)

        if layout.get("underline"):
            gap = float(layout.get("underline_gap", 6))
            line_y = y - gap
            line_color = layout.get("underline_color", color)
            line_width = float(layout.get("underline_width", 0.75))
            pdf_canvas.setStrokeColor(HexColor(line_color))
            pdf_canvas.setLineWidth(line_width)
            if align == "center":
                pdf_canvas.line(x - text_width / 2, line_y, x + text_width / 2, line_y)
            elif align == "right":
                pdf_canvas.line(x - text_width, line_y, x, line_y)
            else:
                pdf_canvas.line(x, line_y, x + text_width, line_y)

    def _draw_preview_watermark(self, pdf_canvas) -> None:
        pdf_canvas.saveState()
        pdf_canvas.setFont(SERIF_BOLD, 72)
        pdf_canvas.setFillColor(HexColor("#CCCCCC"))
        if hasattr(pdf_canvas, "setFillAlpha"):
            pdf_canvas.setFillAlpha(0.22)
        pdf_canvas.translate(self.page_w / 2, self.page_h / 2)
        pdf_canvas.rotate(45)
        pdf_canvas.drawCentredString(0, 0, "PREVIEW")
        pdf_canvas.restoreState()

    def _layout_for(self, key: str) -> Dict[str, Any]:
        return dict(self.layout.get(key) or DEFAULT_FIELD_LAYOUT.get(key) or {})

    @staticmethod
    def _set_fill_from_layout(pdf_canvas, layout: Dict[str, Any], default: str = "#1A1A1A") -> None:
        pdf_canvas.setFillColor(HexColor(layout.get("color", default)))

    def _draw_text(self, pdf_canvas, text: Optional[str], layout_key: str) -> None:
        if not text:
            return
        layout = self._layout_for(layout_key)
        font = layout.get("font", SERIF)
        size = float(layout.get("size", 12))
        x = float(layout.get("x", 0))
        y = float(layout.get("y", 0))
        align = layout.get("align", "left")

        self._set_fill_from_layout(pdf_canvas, layout)
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

    def _draw_wrapped_text(self, pdf_canvas, text: Optional[str], layout_key: str) -> None:
        if not text:
            return
        layout = self._layout_for(layout_key)
        font = layout.get("font", SERIF)
        size = float(layout.get("size", 12))
        x = float(layout.get("x", 0))
        y = float(layout.get("y", 0))
        align = layout.get("align", "left")
        max_width = float(layout.get("max_width", self.page_w - 80))
        line_height = float(layout.get("line_height", size * 1.25))

        self._set_fill_from_layout(pdf_canvas, layout)
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
        align = layout.get("align", "center")
        name_font = layout.get("name_font", SERIF_BOLD)
        title_font = layout.get("title_font", SERIF)
        size = float(layout.get("size", 10))

        name_x = float(layout.get("name_x", 0))
        name_y = float(layout.get("name_y", 0))
        title_y = float(layout.get("title_y", name_y - 14))
        line_y = float(layout.get("line_y", name_y + 14))
        line_width = float(layout.get("line_width", 120))
        line_color = layout.get("line_color", "#A66A28")

        signature_bytes = self._load_image_bytes(signatory.get("signature_url"))
        if signature_bytes:
            sig_x = float(layout.get("signature_x", name_x))
            sig_y = float(layout.get("signature_y", name_y + 40))
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

        pdf_canvas.setStrokeColor(HexColor(line_color))
        pdf_canvas.setLineWidth(1.0)
        if align == "center":
            pdf_canvas.line(name_x - line_width / 2, line_y, name_x + line_width / 2, line_y)
        elif align == "right":
            pdf_canvas.line(name_x - line_width, line_y, name_x, line_y)
        else:
            pdf_canvas.line(name_x, line_y, name_x + line_width, line_y)

        full_name = signatory.get("full_name") or ""
        title = signatory.get("title") or ""

        pdf_canvas.setFont(name_font, size)
        pdf_canvas.setFillColor(HexColor(layout.get("name_color", "#1A1A1A")))
        if align == "center":
            pdf_canvas.drawCentredString(name_x, name_y, full_name)
        elif align == "right":
            pdf_canvas.drawRightString(name_x, name_y, full_name)
        else:
            pdf_canvas.drawString(name_x, name_y, full_name)

        pdf_canvas.setFont(title_font, size)
        pdf_canvas.setFillColor(HexColor(layout.get("title_color", "#A66A28")))
        if align == "center":
            pdf_canvas.drawCentredString(name_x, title_y, title)
        elif align == "right":
            pdf_canvas.drawRightString(name_x, title_y, title)
        else:
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
        for page in writer.pages:
            try:
                page.compress_content_streams()
            except Exception as exc:
                logger.warning("PDF stream compression skipped: %s", exc)


def pdf_string_width(text: str, font: str, size: float) -> float:
    ensure_certificate_fonts()
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


def _ordinal_day(day: int) -> str:
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_display_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def format_display_date_prose(value: date) -> str:
    """e.g. 20th May 2026 — matches the sample certificate."""
    return f"{_ordinal_day(value.day)} {value.strftime('%B %Y')}"


def layout_text_overrides(field_layout: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not field_layout:
        return {}
    text = field_layout.get("text")
    return dict(text) if isinstance(text, dict) else {}


def layout_watermark_config(field_layout: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not field_layout:
        return {}
    watermark = field_layout.get("watermark")
    return dict(watermark) if isinstance(watermark, dict) else {}


def template_watermark_settings(template: Any) -> Dict[str, Any]:
    """Resolve watermark config from template columns with field_layout fallback."""
    layout_wm = layout_watermark_config(getattr(template, "field_layout", None))
    logo_url = getattr(template, "watermark_logo_url", None) or layout_wm.get("logo_url")
    enabled = bool(logo_url)
    if layout_wm.get("enabled") is False:
        enabled = False
    opacity_raw = getattr(template, "watermark_opacity", None)
    if opacity_raw is None:
        opacity = float(layout_wm.get("opacity") or 0.12)
    else:
        opacity = float(opacity_raw)
    style = (
        getattr(template, "watermark_style", None)
        or layout_wm.get("style")
        or "distributed"
    )
    return {
        "watermark_logo_url": logo_url,
        "watermark_enabled": enabled and bool(logo_url),
        "watermark_opacity": max(0.05, min(0.35, opacity)),
        "watermark_style": str(style).lower(),
    }
