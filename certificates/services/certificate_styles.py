"""
Visual tokens and default field layout — matched to the AHBT sample certificate.
"""

from __future__ import annotations

from typing import Any, Dict

from certificates.services.certificate_fonts import SERIF, SERIF_BOLD

A4_WIDTH = 595.28
A4_HEIGHT = 841.89

# Sample certificate palette
COLOR_ACCENT = "#A66A28"  # burnt orange / gold-brown headings
COLOR_ACCENT_DARK = "#8B4513"
COLOR_BODY = "#1A1A1A"
COLOR_FLOURISH = "#1E5A7A"  # teal-blue ornaments
COLOR_SIGNATURE_LINE = "#A66A28"
COLOR_MUTED = "#333333"

DEFAULT_CERTIFICATE_HEADING = "CERTIFICATE"
DEFAULT_CERTIFICATE_SUBHEADING = "OF PARTICIPATION"
DEFAULT_CERT_INTRO = "This is to certify that"

DEFAULT_FIELD_LAYOUT: Dict[str, Any] = {
    "page": {"width": A4_WIDTH, "height": A4_HEIGHT},
    "home_logo": {"x": 52, "y": 792, "max_width": 135, "max_height": 62},
    "invited_logo": {"x": 448, "y": 778, "max_width": 115, "max_height": 58},
    "cert_number": {
        "x": 543,
        "y": 748,
        "font": SERIF,
        "size": 8.5,
        "align": "right",
        "color": COLOR_BODY,
    },
    "certificate_heading": {
        "x": 297.64,
        "y": 688,
        "font": SERIF_BOLD,
        "size": 34,
        "align": "center",
        "color": COLOR_ACCENT,
        "tracking": 1.5,
    },
    "certificate_subheading": {
        "x": 297.64,
        "y": 662,
        "font": SERIF_BOLD,
        "size": 13,
        "align": "center",
        "color": COLOR_ACCENT,
        "draw_flourishes": True,
    },
    "cert_intro": {
        "x": 297.64,
        "y": 628,
        "font": SERIF,
        "size": 13,
        "align": "center",
        "color": COLOR_BODY,
    },
    "participant_name": {
        "x": 297.64,
        "y": 592,
        "size": 34,
        "align": "center",
        "color": COLOR_BODY,
        "underline": True,
        "underline_color": COLOR_BODY,
        "underline_width": 0.75,
        "underline_gap": 6,
    },
    "participation_line": {
        "x": 297.64,
        "y": 548,
        "font": SERIF,
        "size": 12,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": 460,
    },
    "subject_title": {
        "x": 297.64,
        "y": 518,
        "font": SERIF_BOLD,
        "size": 12.5,
        "align": "center",
        "color": COLOR_ACCENT,
        "max_width": 460,
        "line_height": 15,
    },
    "venue_line": {
        "x": 297.64,
        "y": 468,
        "font": SERIF,
        "size": 11.5,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": 460,
        "line_height": 14,
    },
    "date_line": {
        "x": 297.64,
        "y": 438,
        "font": SERIF,
        "size": 11.5,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": 460,
    },
    "cpd_line": {
        "x": 297.64,
        "y": 408,
        "font": SERIF,
        "size": 11.5,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": 460,
        "line_height": 14,
        "optional": True,
    },
    "signatory_1": {
        "name_x": 148,
        "name_y": 118,
        "title_y": 102,
        "signature_x": 148,
        "signature_y": 158,
        "signature_width": 120,
        "signature_height": 44,
        "line_y": 132,
        "line_width": 130,
        "name_font": SERIF_BOLD,
        "title_font": SERIF,
        "name_color": COLOR_BODY,
        "title_color": COLOR_ACCENT,
        "line_color": COLOR_SIGNATURE_LINE,
        "size": 10,
        "align": "center",
    },
    "signatory_2": {
        "name_x": 447,
        "name_y": 118,
        "title_y": 102,
        "signature_x": 447,
        "signature_y": 158,
        "signature_width": 120,
        "signature_height": 44,
        "line_y": 132,
        "line_width": 130,
        "name_font": SERIF_BOLD,
        "title_font": SERIF,
        "name_color": COLOR_BODY,
        "title_color": COLOR_ACCENT,
        "line_color": COLOR_SIGNATURE_LINE,
        "size": 10,
        "align": "center",
    },
    "signatory_center_flourish": {
        "x": 297.64,
        "y": 138,
        "color": COLOR_FLOURISH,
    },
    "watermark": {
        "tile_width": 88,
        "gap_x": 36,
        "gap_y": 44,
        "margin": 48,
        "center_width": 220,
    },
}
