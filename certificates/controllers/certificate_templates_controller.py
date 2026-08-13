import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.controllers.template_file_utils import (
    handle_background_upload,
    handle_signature_upload,
    handle_watermark_upload,
)
from certificates.models.models import CertificateTemplate, CertificateTemplateSignatory
from certificates.models.schemas import (
    CertificateTemplateCreate,
    SignatoryInput,
    template_payload,
)
from database.db_connector import get_db

certificate_templates_bp = Blueprint("certificate_templates", __name__)

DEFAULT_CERTIFICATE_TITLE = "Certificate of Participation"
DEFAULT_PARTICIPATION_PREFIX = "Participated in the training on"
DEFAULT_VENUE_TEMPLATE = "held at {venue}"
DEFAULT_DATE_TEMPLATE = "from {start_date} to {end_date}"
DEFAULT_CPD_TEMPLATE = (
    "from {start_date} to {end_date} and qualified for the award of "
    "{cpd_hours} hours of Continuing Professional Development"
)


def _parse_bool(value, default=True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _parse_json_field(raw_value, field_name: str) -> Tuple[Optional[Any], Optional[str]]:
    if raw_value in (None, ""):
        return None, None
    if isinstance(raw_value, (dict, list)):
        return raw_value, None
    try:
        return json.loads(raw_value), None
    except json.JSONDecodeError:
        return None, f"{field_name} must be valid JSON"


def _parse_signatories(raw_value) -> Tuple[List[SignatoryInput], Optional[str]]:
    parsed, error = _parse_json_field(raw_value, "signatories")
    if error:
        return [], error
    if parsed is None:
        return [], None
    if not isinstance(parsed, list):
        return [], "signatories must be a JSON array"

    signatories: List[SignatoryInput] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            return [], f"signatories[{index}] must be an object"
        try:
            signatories.append(SignatoryInput(**item))
        except Exception as exc:
            return [], f"signatories[{index}] is invalid: {exc}"
    return signatories, None


def _parse_watermark_fields(name: str, form_or_data: Any, *, is_form: bool) -> Tuple[Dict[str, Any], Optional[str]]:
    def get(key: str, default=None):
        if is_form:
            return request.form.get(key, default)
        return form_or_data.get(key, default)

    watermark_logo_url = (get("watermark_logo_url") or "").strip() or None
    watermark_logo_filename = (get("watermark_logo_filename") or "").strip() or None
    watermark_enabled = _parse_bool(get("watermark_enabled"), False)
    watermark_style = (get("watermark_style") or "distributed").strip().lower()
    if watermark_style not in {"distributed", "center"}:
        return {}, "watermark_style must be distributed or center"

    try:
        watermark_opacity = float(get("watermark_opacity") or 0.12)
    except (TypeError, ValueError):
        return {}, "watermark_opacity must be a number"
    watermark_opacity = max(0.05, min(0.35, watermark_opacity))

    if is_form:
        watermark_file = request.files.get("watermark_logo") or request.files.get("watermark")
        if watermark_file and watermark_file.filename:
            watermark_logo_url, watermark_logo_filename, upload_error = handle_watermark_upload(
                watermark_file,
                name,
            )
            if upload_error:
                return {}, upload_error
            watermark_enabled = True

    if watermark_logo_url and not watermark_enabled:
        watermark_enabled = True

    return {
        "watermark_logo_url": watermark_logo_url,
        "watermark_logo_filename": watermark_logo_filename,
        "watermark_opacity": watermark_opacity,
        "watermark_style": watermark_style,
        "watermark_enabled": watermark_enabled,
    }, None


def _parse_create_payload(current_user_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, int]]]:
    is_multipart = bool(request.form) or bool(request.files)

    if is_multipart:
        name = (request.form.get("name") or "").strip()
        if not name:
            return None, ("name is required", 400)

        field_layout, field_layout_error = _parse_json_field(
            request.form.get("field_layout"),
            "field_layout",
        )
        if field_layout_error:
            return None, (field_layout_error, 400)

        signatories, signatories_error = _parse_signatories(request.form.get("signatories"))
        if signatories_error:
            return None, (signatories_error, 400)

        background_url = (request.form.get("background_url") or "").strip() or None
        background_filename = (request.form.get("background_filename") or "").strip() or None

        background_file = request.files.get("background")
        if background_file and background_file.filename:
            background_url, background_filename, upload_error = handle_background_upload(
                background_file,
                name,
            )
            if upload_error:
                return None, (upload_error, 400)
        elif not background_url:
            return None, ("background PDF file is required", 400)

        watermark_fields, watermark_error = _parse_watermark_fields(name, request.form, is_form=True)
        if watermark_error:
            return None, (watermark_error, 400)

        data = {
            "name": name,
            "description": request.form.get("description"),
            "background_url": background_url,
            "background_filename": background_filename,
            **watermark_fields,
            "certificate_title": request.form.get("certificate_title") or DEFAULT_CERTIFICATE_TITLE,
            "participation_prefix": request.form.get("participation_prefix") or DEFAULT_PARTICIPATION_PREFIX,
            "venue_template": request.form.get("venue_template") or DEFAULT_VENUE_TEMPLATE,
            "date_template": request.form.get("date_template") or DEFAULT_DATE_TEMPLATE,
            "cpd_template": request.form.get("cpd_template") or DEFAULT_CPD_TEMPLATE,
            "field_layout": field_layout,
            "is_active": _parse_bool(request.form.get("is_active"), True),
            "signatories": signatories,
            "created_by": current_user_id,
            "updated_by": current_user_id,
        }
        return data, None

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return None, ("name is required", 400)

    background_url = (data.get("background_url") or "").strip()
    if not background_url:
        return None, ("background_url is required (or upload background PDF via multipart)", 400)

    signatories_raw = data.get("signatories") or []
    signatories: List[SignatoryInput] = []
    for index, item in enumerate(signatories_raw):
        try:
            signatories.append(SignatoryInput(**item))
        except Exception as exc:
            return None, (f"signatories[{index}] is invalid: {exc}", 400)

    watermark_fields, watermark_error = _parse_watermark_fields(name, data, is_form=False)
    if watermark_error:
        return None, (watermark_error, 400)

    payload = {
        "name": name,
        "description": data.get("description"),
        "background_url": background_url,
        "background_filename": data.get("background_filename"),
        **watermark_fields,
        "certificate_title": data.get("certificate_title") or DEFAULT_CERTIFICATE_TITLE,
        "participation_prefix": data.get("participation_prefix") or DEFAULT_PARTICIPATION_PREFIX,
        "venue_template": data.get("venue_template") or DEFAULT_VENUE_TEMPLATE,
        "date_template": data.get("date_template") or DEFAULT_DATE_TEMPLATE,
        "cpd_template": data.get("cpd_template") or DEFAULT_CPD_TEMPLATE,
        "field_layout": data.get("field_layout"),
        "is_active": data.get("is_active", True),
        "signatories": signatories,
        "created_by": current_user_id,
        "updated_by": current_user_id,
    }
    return payload, None


def _signature_file_for_order(display_order: int):
    """Match signature_{display_order} or signature-{display_order} upload keys."""
    for key in (f"signature_{display_order}", f"signature-{display_order}"):
        file_storage = request.files.get(key)
        if file_storage and file_storage.filename:
            return file_storage
    return None


def _create_signatories(
    db,
    template: CertificateTemplate,
    signatories: List[SignatoryInput],
) -> List[CertificateTemplateSignatory]:
    created_rows: List[CertificateTemplateSignatory] = []
    for signatory in signatories:
        signature_url = None
        signature_file = _signature_file_for_order(signatory.display_order)
        if signature_file:
            signature_url, upload_error = handle_signature_upload(
                signature_file,
                template.name,
                signatory.display_order,
            )
            if upload_error:
                raise ValueError(upload_error)

        row = CertificateTemplateSignatory(
            template_id=template.id,
            display_order=signatory.display_order,
            full_name=signatory.full_name,
            title=signatory.title,
            signature_url=signature_url,
        )
        db.add(row)
        created_rows.append(row)
    return created_rows


@certificate_templates_bp.route("/certificate-templates", methods=["GET"])
@jwt_required()
def list_certificate_templates():
    """List certificate templates (admin)."""
    db = get_db()
    try:
        rows = (
            db.query(CertificateTemplate)
            .filter(CertificateTemplate.deleted_at.is_(None))
            .order_by(CertificateTemplate.name.asc())
            .all()
        )
        return jsonify({
            "status": "success",
            "data": [template_payload(row) for row in rows],
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_templates_bp.route("/certificate-templates/<int:template_id>", methods=["GET"])
@jwt_required()
def get_certificate_template(template_id: int):
    """Get one certificate template (Group 1 payload)."""
    db = get_db()
    try:
        row = (
            db.query(CertificateTemplate)
            .filter(
                CertificateTemplate.id == template_id,
                CertificateTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Certificate template not found"}), 404
        return jsonify({"status": "success", "data": template_payload(row)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_templates_bp.route("/certificate-templates", methods=["POST"])
@jwt_required()
def create_certificate_template():
    """
    Create a certificate template (Group 1).

    Multipart form fields:
      - name (required)
      - background (PDF/PNG file, required unless background_url provided)
      - watermark_logo (PNG/JPG, optional — tiled or centered on certificate)
      - watermark_opacity (0.05–0.35, default 0.12)
      - watermark_style (distributed | center)
      - watermark_enabled (true when logo uploaded)
      - certificate_title, participation_prefix, venue_template, date_template, cpd_template
      - field_layout (JSON string)
      - signatories (JSON array string)
      - signature_{display_order} files for each signatory (optional PNG/JPG)
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        data, error = _parse_create_payload(current_user_id)
        if error:
            message, status = error
            return jsonify({"status": "error", "message": message}), status

        signatories = data.pop("signatories", [])

        template_data = CertificateTemplateCreate(**data)
        row = CertificateTemplate(**template_data.model_dump())
        db.add(row)
        db.flush()

        if signatories:
            _create_signatories(db, row, signatories)

        db.commit()
        db.refresh(row)

        return jsonify({
            "status": "success",
            "message": "Certificate template created successfully",
            "data": template_payload(row),
        }), 201
    except ValueError as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@certificate_templates_bp.route("/certificate-templates/<int:template_id>", methods=["DELETE"])
@jwt_required()
def delete_certificate_template(template_id: int):
    """Soft-delete a certificate template."""
    db = get_db()
    try:
        row = (
            db.query(CertificateTemplate)
            .filter(
                CertificateTemplate.id == template_id,
                CertificateTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Certificate template not found"}), 404

        row.deleted_at = datetime.utcnow()
        row.updated_by = int(get_jwt_identity())
        db.commit()
        return jsonify({
            "status": "success",
            "message": "Certificate template deleted successfully",
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()
