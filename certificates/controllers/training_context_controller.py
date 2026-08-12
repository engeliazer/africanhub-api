import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.controllers.template_file_utils import handle_signature_upload
from certificates.controllers.training_logo_utils import handle_training_logo_upload
from certificates.models.models import CertificateTrainingContext
from certificates.models.schemas import TrainingContextInput, training_context_payload
from certificates.services.training_context_service import (
    apply_training_context_fields,
    find_training_context,
    get_active_template,
    resolve_subject_title,
    validate_training_context_data,
)
from database.db_connector import get_db

certificate_training_context_bp = Blueprint("certificate_training_context", __name__)


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    if not value:
        raise ValueError("date is required")
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    return date.fromisoformat(text)


def _parse_int(value, default: int = 0) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _parse_json_field(raw_value, field_name: str) -> Tuple[Optional[Any], Optional[str]]:
    if raw_value in (None, ""):
        return None, None
    if isinstance(raw_value, (dict, list)):
        return raw_value, None
    try:
        return json.loads(raw_value), None
    except json.JSONDecodeError:
        return None, f"{field_name} must be valid JSON"


def _parse_payload(current_user_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, int]]]:
    is_multipart = bool(request.form) or bool(request.files)

    if is_multipart:
        training_type = (request.form.get("training_type") or "").strip().lower()
        training_id_raw = request.form.get("training_id")
        if not training_type or not training_id_raw:
            return None, ("training_type and training_id are required", 400)

        signatory_override, signatory_error = _parse_json_field(
            request.form.get("signatory_override"),
            "signatory_override",
        )
        if signatory_error:
            return None, (signatory_error, 400)

        try:
            data = {
                "training_type": training_type,
                "training_id": int(training_id_raw),
                "certificate_template_id": int(request.form.get("certificate_template_id")),
                "host_mode": (request.form.get("host_mode") or "single").strip().lower(),
                "host_organization_name": request.form.get("host_organization_name"),
                "invited_organization_name": request.form.get("invited_organization_name"),
                "subject_title": request.form.get("subject_title"),
                "venue_text": request.form.get("venue_text"),
                "start_date": _parse_date(request.form.get("start_date")),
                "end_date": _parse_date(request.form.get("end_date")),
                "cpd_hours": _parse_int(request.form.get("cpd_hours"), 0),
                "cert_number_pattern": request.form.get("cert_number_pattern"),
                "home_code": request.form.get("home_code"),
                "invited_code": request.form.get("invited_code"),
                "signatory_override": signatory_override,
                "created_by": current_user_id,
                "updated_by": current_user_id,
            }
        except (TypeError, ValueError) as exc:
            return None, (f"Invalid form field: {exc}", 400)
    else:
        body = request.get_json(silent=True) or {}
        try:
            parsed = TrainingContextInput(**body)
            data = parsed.model_dump()
            data["created_by"] = current_user_id
            data["updated_by"] = current_user_id
        except Exception as exc:
            return None, (str(exc), 400)

    validation_error = validate_training_context_data(data)
    if validation_error:
        return None, (validation_error, 400)

    return data, None


def _apply_logo_uploads(data: Dict[str, Any]) -> Optional[str]:
    training_type = data["training_type"]
    training_id = data["training_id"]

    home_file = request.files.get("home_logo")
    if home_file and home_file.filename:
        home_logo_url, error = handle_training_logo_upload(
            home_file, training_type, training_id, "home"
        )
        if error:
            return error
        data["home_logo_url"] = home_logo_url
    elif request.form.get("home_logo_url"):
        data["home_logo_url"] = request.form.get("home_logo_url")

    invited_file = request.files.get("invited_logo")
    if invited_file and invited_file.filename:
        invited_logo_url, error = handle_training_logo_upload(
            invited_file, training_type, training_id, "invited"
        )
        if error:
            return error
        data["invited_logo_url"] = invited_logo_url
    elif request.form.get("invited_logo_url"):
        data["invited_logo_url"] = request.form.get("invited_logo_url")

    return None


def _apply_override_signatures(data: Dict[str, Any]) -> Optional[str]:
    override = data.get("signatory_override")
    if not override or not isinstance(override, list):
        return None

    slug = f"{data['training_type']}-{data['training_id']}"
    updated: List[Dict[str, Any]] = []
    for item in override:
        entry = dict(item)
        display_order = int(entry.get("display_order", 1))
        for key in (f"override_signature_{display_order}", f"signature_{display_order}"):
            file_storage = request.files.get(key)
            if file_storage and file_storage.filename:
                signature_url, error = handle_signature_upload(
                    file_storage,
                    slug,
                    display_order,
                )
                if error:
                    return error
                entry["signature_url"] = signature_url
                break
        updated.append(entry)

    data["signatory_override"] = updated
    return None


@certificate_training_context_bp.route("/certificate-training-contexts", methods=["GET"])
@jwt_required()
def get_training_context_by_training():
    """
    Lookup Group 2 context by training_type + training_id.
    ?training_type=course|subject&training_id=501
    """
    training_type = (request.args.get("training_type") or "").strip().lower()
    training_id_raw = request.args.get("training_id")
    if not training_type or not training_id_raw:
        return jsonify({
            "status": "error",
            "message": "training_type and training_id query params are required",
        }), 400

    db = get_db()
    try:
        row = find_training_context(db, training_type, int(training_id_raw))
        if not row:
            return jsonify({"status": "error", "message": "Training context not found"}), 404
        return jsonify({"status": "success", "data": training_context_payload(row)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_training_context_bp.route("/certificate-training-contexts/<int:context_id>", methods=["GET"])
@jwt_required()
def get_training_context(context_id: int):
    db = get_db()
    try:
        row = (
            db.query(CertificateTrainingContext)
            .filter(
                CertificateTrainingContext.id == context_id,
                CertificateTrainingContext.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Training context not found"}), 404
        return jsonify({"status": "success", "data": training_context_payload(row)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@certificate_training_context_bp.route("/certificate-training-contexts", methods=["POST"])
@jwt_required()
def upsert_training_context():
    """
    Create or update Group 2 training context for a course or subject.

    JSON or multipart. Required identifiers:
      - training_type: course | subject
      - training_id: courses.id or subjects.id
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        data, error = _parse_payload(current_user_id)
        if error:
            message, status = error
            return jsonify({"status": "error", "message": message}), status

        _, template_error = get_active_template(db, data["certificate_template_id"])
        if template_error:
            return jsonify({"status": "error", "message": template_error}), 400

        subject_title, title_error = resolve_subject_title(
            db,
            data["training_type"],
            data["training_id"],
            data.get("subject_title"),
        )
        if title_error:
            return jsonify({"status": "error", "message": title_error}), 404
        data["subject_title"] = subject_title

        logo_error = _apply_logo_uploads(data)
        if logo_error:
            return jsonify({"status": "error", "message": logo_error}), 400

        signature_error = _apply_override_signatures(data)
        if signature_error:
            return jsonify({"status": "error", "message": signature_error}), 400

        existing = find_training_context(db, data["training_type"], data["training_id"])
        if existing:
            apply_training_context_fields(existing, data)
            row = existing
            message = "Training context updated successfully"
            status_code = 200
        else:
            row = CertificateTrainingContext(**data)
            db.add(row)
            message = "Training context created successfully"
            status_code = 201

        db.commit()
        db.refresh(row)
        return jsonify({
            "status": "success",
            "message": message,
            "data": training_context_payload(row),
        }), status_code
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()


@certificate_training_context_bp.route("/certificate-training-contexts/<int:context_id>", methods=["DELETE"])
@jwt_required()
def delete_training_context(context_id: int):
    db = get_db()
    try:
        row = (
            db.query(CertificateTrainingContext)
            .filter(
                CertificateTrainingContext.id == context_id,
                CertificateTrainingContext.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Training context not found"}), 404

        row.deleted_at = datetime.utcnow()
        row.updated_by = int(get_jwt_identity())
        db.commit()
        return jsonify({
            "status": "success",
            "message": "Training context deleted successfully",
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        db.close()
