"""Register certificate fonts (script name + serif fallbacks)."""

from __future__ import annotations

import os
from functools import lru_cache

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

SCRIPT_FONT = "CertificateScript"
SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SERIF_ITALIC = "Times-Italic"
SERIF_BOLD_ITALIC = "Times-BoldItalic"

_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
_SCRIPT_FILE = os.path.join(_FONT_DIR, "GreatVibes-Regular.ttf")


@lru_cache(maxsize=1)
def ensure_certificate_fonts() -> None:
    if SCRIPT_FONT in pdfmetrics.getRegisteredFontNames():
        return
    if os.path.isfile(_SCRIPT_FILE):
        pdfmetrics.registerFont(TTFont(SCRIPT_FONT, _SCRIPT_FILE))


def participant_name_font() -> str:
    ensure_certificate_fonts()
    if SCRIPT_FONT in pdfmetrics.getRegisteredFontNames():
        return SCRIPT_FONT
    return SERIF_BOLD_ITALIC
