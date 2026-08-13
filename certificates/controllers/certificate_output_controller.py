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
from certificates.services.certificate_renderer import MAX_JSON_INLINE_PDF_BYTES
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
    ?source=event&render=true to also attempt PDF generation and report byte size.
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
    Render a certificate PDF for one participant without saving it.

    Uses the training context template, logos, signatories, and participant data.
    Adds a PREVIEW watermark and cert_number = PREVIEW.

    Query params:
      - source=event (default for event training contexts) | certificate
      - format=json — metadata + optional small base64 PDF (see include_pdf)
      - include_pdf=1 — embed pdf_base64 only when raw PDF <= 2 MB
      - debug=1 — include traceback on errors (JSON only)
    """
    db = get_db()
    json_mode = _wants_json_preview()
    include_trace = request.args.get("debug") == "1"

    try:
        from certificates.services.certificate_render_service import (
            render_participant_certificate_pdf,
        )

        source = (request.args.get("source") or "").strip().lower() or None
        pdf_bytes, meta, error = render_participant_certificate_pdf(
            db,
            context_id,
            participant_id,
            preview=True,
            source=source,
        )

        if error:
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
            return _certificate_render_error_response(
                "Certificate render returned empty PDF",
                context_id=context_id,
                participant_id=participant_id,
            )

        filename = f"certificate-preview-{participant_id}.pdf"
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
                "message": "Certificate preview generated",
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

    Generates the PDF, stores it, and returns the certificate record.
    """
    db = get_db()
    try:
        from certificates.services.certificate_render_service import (
            build_render_data,
            get_participant_or_error,
            get_training_context_or_error,
            resolve_render_participant,
        )
        from certificates.services.certificate_renderer import CertificateRenderer

        current_user_id = int(get_jwt_identity())
        context, context_error = get_training_context_or_error(db, context_id)
        if context_error:
            return jsonify({"status": "error", "message": context_error}), 404

        participant, participant_error = get_participant_or_error(
            db,
            context_id,
            participant_id,
        )
        if participant_error:
            return jsonify({
                "status": "error",
                "message": (
                    "Participant must be on the certificate roster before issuing. "
                    "For events, import the training calendar roster first: "
                    "POST .../participants/import-event-roster"
                ),
            }), 404

        if participant.certificate_id:
            existing = (
                db.query(Certificate)
                .filter(
                    Certificate.id == participant.certificate_id,
                    Certificate.deleted_at.is_(None),
                )
                .first()
            )
            if existing:
                return jsonify({
                    "status": "success",
                    "message": "Certificate already issued",
                    "data": certificate_output_payload(existing),
                }), 200

        identity, _, identity_error = resolve_render_participant(
            db,
            context,
            participant_id,
            source="certificate",
        )
        if identity_error:
            return jsonify({"status": "error", "message": identity_error}), 400

        render_data, build_error = build_render_data(
            db,
            context,
            identity,
            certificate_participant=participant,
            preview=False,
        )
        if build_error:
            return jsonify({"status": "error", "message": build_error}), 400

        meta = render_data["meta"]
        pdf_bytes = CertificateRenderer(render_data).render_pdf_bytes()

        certificate = Certificate(
            training_context_id=context.id,
            participant_id=participant.id,
            training_id=context.training_id,
            cert_number=meta["cert_number"],
            qualifies_for_cpd=meta["qualifies_for_cpd"],
            pdf_url="",
            created_by=current_user_id,
            updated_by=current_user_id,
        )
        db.add(certificate)
        db.flush()

        pdf_url, _ = save_certificate_pdf(
            pdf_bytes,
            context.training_id,
            certificate_id=certificate.id,
        )
        certificate.pdf_url = pdf_url
        participant.certificate_id = certificate.id
        participant.updated_by = current_user_id

        db.commit()
        db.refresh(certificate)

        return jsonify({
            "status": "success",
            "message": "Certificate issued successfully",
            "data": certificate_output_payload(certificate),
        }), 201
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
