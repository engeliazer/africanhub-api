"""
Public certificate verification — no authentication required.
"""

import os

from flask import Blueprint, Response, jsonify, request, send_file

from certificates.services.certificate_verification_service import (
    build_verification_payload,
    build_verification_pdf_url,
    resolve_verification_pdf_path,
)
from database.db_connector import get_db

certificate_public_bp = Blueprint("certificate_public", __name__)


def _serial_no_from_request() -> str:
    return (request.args.get("serial_no") or "").strip()


@certificate_public_bp.route("/certificates/public/verify", methods=["GET"])
def verify_certificate_json():
    """JSON verification details for a certificate serial number."""
    serial_no = _serial_no_from_request()
    db = get_db()
    try:
        payload, error = build_verification_payload(db, serial_no)
        if error:
            return jsonify({"status": "error", "message": error}), 404
        return jsonify({"status": "success", "data": payload}), 200
    finally:
        db.close()


@certificate_public_bp.route("/certificates/public/verify/pdf", methods=["GET"])
def verify_certificate_pdf():
    """Download or inline-view the issued certificate PDF (public, no auth)."""
    serial_no = _serial_no_from_request()
    db = get_db()
    try:
        local_path, error = resolve_verification_pdf_path(db, serial_no)
        if error:
            return jsonify({"status": "error", "message": error}), 404
        if not local_path or not os.path.isfile(local_path):
            return jsonify({"status": "error", "message": "Certificate PDF file not found"}), 404

        inline = (request.args.get("inline") or "1").strip().lower() in {"1", "true", "yes"}
        return send_file(
            local_path,
            mimetype="application/pdf",
            as_attachment=not inline,
            download_name=f"certificate-{serial_no.replace('/', '-')}.pdf",
        )
    finally:
        db.close()


@certificate_public_bp.route("/certificates/public/verify/view", methods=["GET"])
def verify_certificate_view():
    """Simple public HTML page to verify and display an issued certificate."""
    serial_no = _serial_no_from_request()
    db = get_db()
    try:
        payload, error = build_verification_payload(db, serial_no)
        if error:
            html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Certificate verification</title>
<style>
body {{ font-family: Georgia, serif; margin: 2rem; color: #1a1a1a; }}
.card {{ max-width: 720px; margin: 0 auto; border: 1px solid #ddd; padding: 1.5rem; border-radius: 8px; }}
.bad {{ color: #b00020; }}
</style></head><body><div class="card">
<h1>Certificate verification</h1>
<p class="bad">{error}</p>
</div></body></html>"""
            return Response(html, mimetype="text/html; charset=utf-8"), 404

        issued = payload.get("valid")
        status_label = "Verified" if issued else "Not yet issued"
        status_color = "#1b5e20" if issued else "#8a6d00"
        pdf_block = ""
        if issued and payload.get("serial_no"):
            pdf_url = build_verification_pdf_url(payload["serial_no"]) + "&inline=1"
            pdf_block = f"""
<p><a href="{pdf_url}" target="_blank" rel="noopener">Open certificate PDF</a></p>
<iframe src="{pdf_url}" title="Certificate PDF" width="100%" height="720" style="border:1px solid #ccc;"></iframe>
"""

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Certificate verification — {payload.get("serial_no", "")}</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; margin: 0; background: #f7f5f0; color: #1a1a1a; }}
.wrap {{ max-width: 900px; margin: 0 auto; padding: 1.5rem; }}
.card {{ background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 1.5rem 1.75rem; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
.badge {{ display: inline-block; padding: .35rem .75rem; border-radius: 999px; color: #fff; background: {status_color}; font-size: .9rem; }}
.meta {{ margin: 1rem 0; line-height: 1.6; }}
.meta dt {{ font-weight: bold; margin-top: .75rem; }}
.meta dd {{ margin: 0; }}
iframe {{ margin-top: 1rem; background: #fff; }}
</style></head><body><div class="wrap"><div class="card">
<h1>Certificate verification</h1>
<p><span class="badge">{status_label}</span></p>
<p>{payload.get("message", "")}</p>
<dl class="meta">
<dt>Serial number</dt><dd>{payload.get("serial_no") or "—"}</dd>
<dt>Participant</dt><dd>{payload.get("participant_name") or "—"}</dd>
<dt>Training</dt><dd>{payload.get("subject_title") or "—"}</dd>
<dt>Venue</dt><dd>{payload.get("venue_text") or "—"}</dd>
<dt>Dates</dt><dd>{payload.get("start_date") or "—"} to {payload.get("end_date") or "—"}</dd>
<dt>Host organization</dt><dd>{payload.get("host_organization_name") or "—"}</dd>
</dl>
{pdf_block}
</div></div></body></html>"""
        return Response(html, mimetype="text/html; charset=utf-8"), 200
    finally:
        db.close()
