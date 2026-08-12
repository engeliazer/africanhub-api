#!/usr/bin/env python3
"""Verify certificate PDF dependencies (run inside app venv on the server)."""

import sys


def main() -> int:
    missing = []
    for module_name in ("pypdf", "reportlab", "PIL"):
        try:
            __import__(module_name)
        except ImportError as exc:
            missing.append(f"{module_name}: {exc}")

    if missing:
        print("FAIL: certificate PDF dependencies missing:")
        for line in missing:
            print(f"  - {line}")
        print("  Fix: source venv/bin/activate && pip install pypdf 'reportlab>=4.0.4,<5' Pillow")
        return 1

    try:
        from io import BytesIO

        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas

        from certificates.services.certificate_renderer import CertificateRenderer
    except Exception as exc:
        print(f"FAIL: could not import certificate renderer: {exc}")
        return 1

    overlay = BytesIO()
    c = canvas.Canvas(overlay, pagesize=(595.28, 841.89))
    c.drawString(100, 400, "Certificate dependency check OK")
    c.save()

    reader = PdfReader(BytesIO(overlay.getvalue()))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    out = BytesIO()
    writer.write(out)

    render_data = {
        "preview": True,
        "certificate_title": "Test",
        "participant_name": "Test User",
        "participation_line": "Participated in",
        "subject_title": "Subject",
        "venue_line": "Venue",
        "date_line": "Dates",
        "cpd_line": "",
        "qualifies_for_cpd": False,
        "cert_number": "PREVIEW",
        "show_home_logo": False,
        "show_invited_logo": False,
        "signatories": [],
        "template": {"background_url": "inline://test", "field_layout": None},
    }

    class _TestRenderer(CertificateRenderer):
        def _read_background_bytes(self):
            return out.getvalue()

    pdf = _TestRenderer(render_data).render_pdf_bytes()
    print(f"OK: certificate PDF render works ({len(pdf)} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
