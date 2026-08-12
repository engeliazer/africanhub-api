"""
Certificate preview and issuance (Group 4).
"""

import logging
import os
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.controllers.certificate_file_utils import save_certificate_pdf
from certificates.models.models import Certificate
from certificates.models.schemas import certificate_output_payload
from certificates.services.certificate_render_service import (
    build_render_data,
    get_participant_or_error,
    get_training_context_or_error,
    render_participant_certificate_pdf,
    resolve_render_participant,
)
from certificates.services.certificate_renderer import CertificateRenderer
from certificates.services.storage_path_utils import storage_url_to_local_path
from database.db_connector import get_db

logger = logging.getLogger(__name__)

certificate_output_bp = Blueprint("certificate_output", __name__)


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
      - source=certificate (default) | event
        For event training contexts, source=event uses training calendar
        roster ids from event_participants. If omitted, certificate roster
        is checked first, then event roster as fallback.
    """
    db = get_db()
    try:
        source = (request.args.get("source") or "").strip().lower() or None
        pdf_bytes, meta, error = render_participant_certificate_pdf(
            db,
            context_id,
            participant_id,
            preview=True,
            source=source,
        )
        if error:
            status = 404 if "not found" in error.lower() else 400
            return jsonify({"status": "error", "message": error}), status

        if not pdf_bytes:
            return jsonify({"status": "error", "message": "Certificate render returned empty PDF"}), 500

        filename = f"certificate-preview-{participant_id}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=filename,
        )
    except Exception as exc:
        logger.exception(
            "preview_participant_certificate context=%s participant=%s: %s",
            context_id,
            participant_id,
            exc,
        )
        return jsonify({"status": "error", "message": str(exc)}), 500
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
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
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
