#!/usr/bin/env python3
"""Verify invitation PDF dependencies (run inside app venv on the server)."""

import sys


def main() -> int:
    try:
        from io import BytesIO

        import requests  # noqa: F401
        from jinja2 import Environment  # noqa: F401
        from markupsafe import Markup  # noqa: F401
        from PIL import Image  # noqa: F401
        from pypdf import PdfReader  # noqa: F401
        from reportlab.pdfgen import canvas  # noqa: F401
        from xhtml2pdf import pisa
    except ImportError as e:
        print("FAIL: invitation PDF dependencies are not installed.")
        print(f"  Import error: {e}")
        print("  Fix: source venv/bin/activate && pip install -r requirements.txt")
        return 1

    buf = BytesIO()
    status = pisa.CreatePDF(
        "<html><body><p>Invitation PDF dependency check OK</p></body></html>",
        dest=buf,
        encoding="utf-8",
    )
    if status.err:
        print("FAIL: xhtml2pdf import succeeded but PDF generation failed.")
        return 1

    print(f"OK: xhtml2pdf works ({len(buf.getvalue())} byte test PDF).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
