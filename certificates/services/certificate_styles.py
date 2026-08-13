"""
Visual tokens and default field layout — matched to the AHBT sample certificate.
"""

from __future__ import annotations

from typing import Any, Dict

from certificates.services.certificate_fonts import SERIF, SERIF_BOLD

A4_WIDTH = 595.28
A4_HEIGHT = 841.89

# Inner gold border on the AHBT background — body text stays inside this frame.
INNER_BORDER_INSET = 78
CONTENT_PADDING = 12
CONTENT_LEFT = INNER_BORDER_INSET + CONTENT_PADDING
CONTENT_RIGHT = A4_WIDTH - INNER_BORDER_INSET - CONTENT_PADDING
CONTENT_MAX_WIDTH = CONTENT_RIGHT - CONTENT_LEFT
CONTENT_CENTER_X = A4_WIDTH / 2
INNER_FRAME_TOP_Y = A4_HEIGHT - INNER_BORDER_INSET
CERT_NUMBER_Y = INNER_FRAME_TOP_Y - CONTENT_PADDING + 16

# Signatory blocks — one per inner-frame half, centered with padded signature lines.
SIGNATORY_HALF_WIDTH = CONTENT_MAX_WIDTH / 2
SIGNATORY_SIDE_PADDING = 18
SIGNATORY_LINE_WIDTH = SIGNATORY_HALF_WIDTH - (2 * SIGNATORY_SIDE_PADDING)
SIGNATORY_1_CENTER_X = CONTENT_LEFT + SIGNATORY_HALF_WIDTH / 2
SIGNATORY_2_CENTER_X = CONTENT_CENTER_X + SIGNATORY_HALF_WIDTH / 2
SIGNATORY_SIGNATURE_WIDTH = min(120, SIGNATORY_LINE_WIDTH - 10)

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
    "home_logo": {"x": 52, "y": 768, "max_width": 135, "max_height": 62},
    "invited_logo": {"x": 448, "y": 754, "max_width": 115, "max_height": 58},
    "cert_number": {
        "x": CONTENT_RIGHT,
        "y": CERT_NUMBER_Y,
        "font": SERIF,
        "size": 15,
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
        "y": 595,
        "font": SERIF,
        "size": 13,
        "align": "center",
        "color": COLOR_BODY,
    },
    "participant_name": {
        "x": 297.64,
        "y": 548,
        "size": 34,
        "align": "center",
        "color": COLOR_BODY,
        "underline": True,
        "underline_color": COLOR_BODY,
        "underline_width": 0.75,
        "underline_gap": 6,
    },
    "participation_line": {
        "x": CONTENT_CENTER_X,
        "y": 488,
        "font": SERIF,
        "size": 24,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": CONTENT_MAX_WIDTH,
        "line_height": 28,
        "gap_after": 14,
    },
    "subject_title": {
        "x": CONTENT_CENTER_X,
        "y": 448,
        "font": SERIF_BOLD,
        "size": 25,
        "align": "center",
        "color": COLOR_ACCENT,
        "max_width": CONTENT_MAX_WIDTH,
        "line_height": 28,
        "gap_after": 22,
    },
    "venue_line": {
        "x": CONTENT_CENTER_X,
        "y": 378,
        "font": SERIF,
        "size": 18,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": CONTENT_MAX_WIDTH,
        "line_height": 18,
        "gap_after": 4,
    },
    "date_line": {
        "x": CONTENT_CENTER_X,
        "y": 342,
        "font": SERIF,
        "size": 18,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": CONTENT_MAX_WIDTH,
        "line_height": 18,
        "gap_after": 8,
    },
    "cpd_line": {
        "x": CONTENT_CENTER_X,
        "y": 306,
        "font": SERIF,
        "size": 23,
        "align": "center",
        "color": COLOR_BODY,
        "max_width": CONTENT_MAX_WIDTH,
        "line_height": 28,
        "gap_after": 8,
        "optional": True,
    },
    "signatory_1": {
        "name_x": SIGNATORY_1_CENTER_X,
        "name_y": 128,
        "title_y": 112,
        "signature_x": SIGNATORY_1_CENTER_X,
        "signature_y": 152,
        "signature_width": SIGNATORY_SIGNATURE_WIDTH,
        "signature_height": 44,
        "line_y": 145,
        "line_width": SIGNATORY_LINE_WIDTH,
        "name_font": SERIF_BOLD,
        "title_font": SERIF,
        "name_color": COLOR_BODY,
        "title_color": COLOR_ACCENT,
        "line_color": COLOR_SIGNATURE_LINE,
        "size": 10,
        "align": "center",
    },
    "signatory_2": {
        "name_x": SIGNATORY_2_CENTER_X,
        "name_y": 128,
        "title_y": 112,
        "signature_x": SIGNATORY_2_CENTER_X,
        "signature_y": 152,
        "signature_width": SIGNATORY_SIGNATURE_WIDTH,
        "signature_height": 44,
        "line_y": 145,
        "line_width": SIGNATORY_LINE_WIDTH,
        "name_font": SERIF_BOLD,
        "title_font": SERIF,
        "name_color": COLOR_BODY,
        "title_color": COLOR_ACCENT,
        "line_color": COLOR_SIGNATURE_LINE,
        "size": 10,
        "align": "center",
    },
    "signatory_center_flourish": {
        "x": CONTENT_CENTER_X,
        "y": 151,
        "color": COLOR_FLOURISH,
    },
    "verification_qr": {
        "x": CONTENT_CENTER_X,
        "y": 210,
        "size": 64,
    },
    "watermark": {
        "tile_width": 110,
        "gap_x": 28,
        "gap_y": 36,
        "margin": 40,
        "center_width": 260,
    },
}
