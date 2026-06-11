#!/usr/bin/env python3
"""Verify invitation PDF dependencies (run inside app venv on the server)."""

import sys


def main() -> int:
    try:
        from xhtml2pdf import pisa
        from io import BytesIO
    except ImportError as e:
        print("FAIL: xhtml2pdf is not installed.")
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
