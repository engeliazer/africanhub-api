"""
Certificate preview and issuance (Group 4).
"""

import base64
import logging
import os
import traceback
from typing import Optional

from flask import Blueprint, Response, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.controllers.certificate_file_utils import save_certificate_pdf
from certificates.models.models import Certificate
from certificates.models.schemas import certificate_output_payload
from certificates.services.certificate_issue_service import (
    get_participant_certificate,
    issue_certificate_for_participant,
)
from certificates.services.certificate_renderer import MAX_JSON_INLINE_PDF_BYTES
from certificates.services.storage_path_utils import storage_url_to_local_path
from database.db_connector import get_db

logger = logging.getLogger(__name__)

certificate_output_bp = Blueprint("certificate_output", __name__)

# Application-level error code for certificate preview/render failures (JSON body).
CERTIFICATE_RENDER_ERROR_STATUS = 105


def _certificate_render_error_response(
    message: str,
    *,
    exc: Optional[BaseException] = None,
    context_id: Optional[int] = None,
    participant_id: Optional[int] = None,
    include_trace: bool = False,
):
    body = {
        "status": CERTIFICATE_RENDER_ERROR_STATUS,
        "message": message,
        "error_type": type(exc).__name__ if exc else "CertificateRenderError",
    }
    if context_id is not None:
        body["context_id"] = context_id
    if participant_id is not None:
        body["participant_id"] = participant_id
    if include_trace and exc is not None:
        body["trace"] = traceback.format_exc()
    return jsonify(body), 500


def _wants_json_preview() -> bool:
    fmt = (request.args.get("format") or "").strip().lower()
    if fmt in {"json", "debug"}:
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept and "application/pdf" not in accept


@certificate_output_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>/preview-check",
    methods=["GET"],
)
@jwt_required()
def preview_participant_certificate_check(context_id: int, participant_id: int):
    """
    Diagnose certificate preview readiness (JSON — use when preview returns 502).
    Requires a confirmed certificate_participants row.
    ?render=true to also attempt PDF generation and report byte size.
    """
    db = get_db()
    try:
        from certificates.services.certificate_render_service import diagnose_certificate_preview

        source = (request.args.get("source") or "").strip().lower() or None
        try_render = (request.args.get("render") or "").strip().lower() in {"1", "true", "yes"}
        data = diagnose_certificate_preview(
            db,
            context_id,
            participant_id,
            source=source,
            try_render=try_render,
        )
        if data.get("ready"):
            return jsonify({"status": "success", "data": data}), 200
        return jsonify({
            "status": CERTIFICATE_RENDER_ERROR_STATUS,
            "message": "Certificate preview is not ready",
            "data": data,
        }), 500
    except BaseException as exc:
        logger.exception("preview_check failed: %s", exc)
        return _certificate_render_error_response(
            str(exc) or "Preview check failed",
            exc=exc,
            context_id=context_id,
            participant_id=participant_id,
            include_trace=request.args.get("debug") == "1",
        )
    finally:
        db.close()


@certificate_output_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>/preview",
    methods=["GET"],
)
@jwt_required()
def preview_participant_certificate(context_id: int, participant_id: int):
    """
    Return the official certificate PDF for one confirmed roster participant.

    Confirmed participants are issued automatically when added to the roster. This
    endpoint returns the stored certificate PDF (and issues it first if missing).

    Query params:
      - format=json — metadata + optional small base64 PDF (see include_pdf)
      - include_pdf=1 — embed pdf_base64 only when raw PDF <= 2 MB
      - debug=1 — include traceback on errors (JSON only)
    """
    db = get_db()
    json_mode = _wants_json_preview()
    include_trace = request.args.get("debug") == "1"
    current_user_id = int(get_jwt_identity())

    try:
        from certificates.services.certificate_issue_service import (
            get_participant_certificate_pdf,
        )

        source = (request.args.get("source") or "").strip().lower() or None
        pdf_bytes, meta, error = get_participant_certificate_pdf(
            db,
            context_id,
            participant_id,
            current_user_id,
            source=source,
            auto_issue=True,
        )

        if error:
            db.rollback()
            if json_mode:
                return jsonify({
                    "status": CERTIFICATE_RENDER_ERROR_STATUS,
                    "message": error,
                    "context_id": context_id,
                    "participant_id": participant_id,
                    "meta": meta,
                }), 500
            return jsonify({"status": "error", "message": error}), (
                404 if "not found" in error.lower() else 400
            )

        if not pdf_bytes:
            db.rollback()
            return _certificate_render_error_response(
                "Certificate render returned empty PDF",
                context_id=context_id,
                participant_id=participant_id,
            )

        db.commit()
        filename = f"{(meta or {}).get('cert_number', participant_id)}.pdf".replace("/", "-")
        pdf_size = len(pdf_bytes)

        if json_mode:
            payload = {
                "context_id": context_id,
                "participant_id": participant_id,
                "filename": filename,
                "pdf_size_bytes": pdf_size,
                "content_type": "application/pdf",
                "meta": meta,
            }
            include_pdf = (request.args.get("include_pdf") or "").strip().lower() in {
                "1",
                "true",
                "yes",
            }
            if include_pdf and pdf_size <= MAX_JSON_INLINE_PDF_BYTES:
                payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
            elif include_pdf:
                return jsonify({
                    "status": CERTIFICATE_RENDER_ERROR_STATUS,
                    "message": (
                        f"PDF too large for JSON embedding ({pdf_size} bytes). "
                        "Omit format=json to receive application/pdf directly."
                    ),
                    "context_id": context_id,
                    "participant_id": participant_id,
                    "data": payload,
                }), 413
            else:
                payload["hint"] = (
                    "Omit format=json (or send Accept: application/pdf) to download "
                    "the PDF directly. Use include_pdf=1 only for small previews."
                )

            return jsonify({
                "status": "success",
                "message": "Certificate retrieved",
                "data": payload,
            }), 200

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except BaseException as exc:
        db.rollback()
        logger.exception(
            "preview_participant_certificate context=%s participant=%s: %s",
            context_id,
            participant_id,
            exc,
        )
        return _certificate_render_error_response(
            str(exc) or "Certificate preview failed",
            exc=exc,
            context_id=context_id,
            participant_id=participant_id,
            include_trace=include_trace,
        )
    finally:
        db.close()


@certificate_output_bp.route(
    "/certificate-training-contexts/<int:context_id>/participants/<int:participant_id>/certificate",
    methods=["POST"],
)
@jwt_required()
def generate_participant_certificate(context_id: int, participant_id: int):
    """
    Issue a certificate for one participant (Group 4 output).

    Returns the existing certificate when already issued; otherwise generates,
    stores the PDF, and returns the certificate record.
    """
    db = get_db()
    try:
        from certificates.services.certificate_render_service import (
            get_confirmed_participant_or_error,
            get_training_context_or_error,
        )

        current_user_id = int(get_jwt_identity())
        context, context_error = get_training_context_or_error(db, context_id)
        if context_error:
            return jsonify({"status": "error", "message": context_error}), 404

        participant, participant_error = get_confirmed_participant_or_error(
            db,
            context_id,
            participant_id,
        )
        if participant_error:
            return jsonify({
                "status": "error",
                "message": participant_error,
            }), 404 if "not found" in participant_error.lower() else 400

        existing = get_participant_certificate(db, participant)
        if existing and existing.pdf_url:
            return jsonify({
                "status": "success",
                "message": "Certificate already issued",
                "data": certificate_output_payload(existing),
            }), 200

        certificate, issue_error = issue_certificate_for_participant(
            db,
            context,
            participant,
            current_user_id,
        )
        if issue_error:
            db.rollback()
            return jsonify({"status": "error", "message": issue_error}), 400

        db.commit()
        db.refresh(certificate)

        return jsonify({
            "status": "success",
            "message": "Certificate issued successfully",
            "data": certificate_output_payload(certificate),
        }), 201 if existing is None else 200
    except BaseException as exc:
        db.rollback()
        logger.exception("generate_participant_certificate: %s", exc)
        return _certificate_render_error_response(
            str(exc) or "Certificate generation failed",
            exc=exc,
            context_id=context_id,
            participant_id=participant_id,
        )
    finally:
        db.close()


@certificate_output_bp.route("/certificates/<int:certificate_id>", methods=["GET"])
@jwt_required()
def get_certificate(certificate_id: int):
    """Fetch one issued certificate record (Group 4)."""
    db = get_db()
    try:
        row = (
            db.query(Certificate)
            .filter(
                Certificate.id == certificate_id,
                Certificate.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Certificate not found"}), 404
        return jsonify({
            "status": "success",
            "data": certificate_output_payload(row),
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_output_bp.route("/certificates/<int:certificate_id>/download", methods=["GET"])
@jwt_required()
def download_certificate(certificate_id: int):
    """Download the stored certificate PDF."""
    db = get_db()
    try:
        row = (
            db.query(Certificate)
            .filter(
                Certificate.id == certificate_id,
                Certificate.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Certificate not found"}), 404

        local_path = storage_url_to_local_path(row.pdf_url)
        if not local_path or not os.path.isfile(local_path):
            return jsonify({"status": "error", "message": "Certificate file not found"}), 404

        filename = f"{row.cert_number.replace('/', '-')}.pdf"
        return send_file(
            local_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()
