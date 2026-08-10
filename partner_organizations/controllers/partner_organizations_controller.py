from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db_connector import get_db
from partner_organizations.models.models import PartnerOrganization
from partner_organizations.models.schemas import (
    PartnerOrganizationCreate,
    PartnerOrganizationUpdate,
    PartnerOrganizationInDB,
)
from partner_organizations.controllers.logo_utils import handle_partner_logo_upload
from datetime import datetime

partner_organizations_bp = Blueprint("partner_organizations", __name__)


def _parse_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _parse_create_payload(current_user_id):
    if request.form:
        data = {
            "name": request.form.get("name"),
            "website_link": request.form.get("website_link"),
            "is_active": _parse_bool(request.form.get("is_active"), True),
        }
        logo_url = None
        if "logo" in request.files:
            logo_file = request.files["logo"]
            if logo_file and logo_file.filename:
                logo_url = handle_partner_logo_upload(logo_file, data["name"] or "org")
                if not logo_url:
                    return None, (
                        "Invalid logo file. Allowed: JPG, PNG, GIF, WEBP, SVG.",
                        400,
                    )
        elif request.form.get("logo"):
            logo_url = request.form.get("logo")
        data["logo"] = logo_url
    else:
        data = request.get_json() or {}
        if not data.get("name"):
            return None, ("name is required", 400)

    data["created_by"] = current_user_id
    data["updated_by"] = current_user_id
    if not data.get("website_link"):
        data["website_link"] = None
    return data, None


def _parse_update_payload(organization_fallback_name: str, current_user_id):
    if request.form:
        data = {}
        for field in ("name", "website_link", "is_active", "logo"):
            if field in request.form and request.form.get(field) is not None:
                if field == "is_active":
                    data[field] = _parse_bool(request.form.get(field))
                elif field == "logo" and not request.files.get("logo"):
                    data[field] = request.form.get("logo")
                elif field != "logo":
                    data[field] = request.form.get(field)

        if "logo" in request.files:
            logo_file = request.files["logo"]
            if logo_file and logo_file.filename:
                org_name = data.get("name", organization_fallback_name)
                logo_url = handle_partner_logo_upload(logo_file, org_name)
                if not logo_url:
                    return None, (
                        "Invalid logo file. Allowed: JPG, PNG, GIF, WEBP, SVG.",
                        400,
                    )
                data["logo"] = logo_url
    else:
        data = request.get_json() or {}

    data["updated_by"] = current_user_id
    if "website_link" in data and not data.get("website_link"):
        data["website_link"] = None
    return data, None


@partner_organizations_bp.route("/partner-organizations", methods=["GET"])
@jwt_required()
def list_partner_organizations():
    """List all partner organizations (admin)."""
    try:
        db = get_db()
        rows = (
            db.query(PartnerOrganization)
            .filter(PartnerOrganization.deleted_at.is_(None))
            .order_by(PartnerOrganization.name.asc())
            .all()
        )
        return jsonify({
            "status": "success",
            "data": [PartnerOrganizationInDB.from_orm(row).dict() for row in rows],
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@partner_organizations_bp.route("/partner-organizations/public", methods=["GET"])
def list_partner_organizations_public():
    """Public list of active partner organizations for the website (no auth)."""
    try:
        db = get_db()
        rows = (
            db.query(PartnerOrganization)
            .filter(
                PartnerOrganization.deleted_at.is_(None),
                PartnerOrganization.is_active == True,
            )
            .order_by(PartnerOrganization.name.asc())
            .all()
        )
        data = [
            {
                "id": row.id,
                "name": row.name,
                "logo": row.logo,
                "website_link": row.website_link,
            }
            for row in rows
        ]
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@partner_organizations_bp.route("/partner-organizations/<int:org_id>", methods=["GET"])
@jwt_required()
def get_partner_organization(org_id):
    """Get one partner organization (admin)."""
    try:
        db = get_db()
        row = (
            db.query(PartnerOrganization)
            .filter(
                PartnerOrganization.id == org_id,
                PartnerOrganization.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Partner organization not found"}), 404
        return jsonify({
            "status": "success",
            "data": PartnerOrganizationInDB.from_orm(row).dict(),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@partner_organizations_bp.route("/partner-organizations", methods=["POST"])
@jwt_required()
def create_partner_organization():
    """Create a partner organization (JSON or multipart with logo file)."""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        data, error = _parse_create_payload(current_user_id)
        if error:
            message, status = error
            return jsonify({"status": "error", "message": message}), status

        org_data = PartnerOrganizationCreate(**data)
        row = PartnerOrganization(**org_data.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({
            "status": "success",
            "message": "Partner organization created successfully",
            "data": PartnerOrganizationInDB.from_orm(row).dict(),
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        db.close()


@partner_organizations_bp.route("/partner-organizations/<int:org_id>", methods=["PUT"])
@jwt_required()
def update_partner_organization(org_id):
    """Update a partner organization (JSON or multipart with logo file)."""
    try:
        db = get_db()
        current_user_id = get_jwt_identity()
        row = (
            db.query(PartnerOrganization)
            .filter(
                PartnerOrganization.id == org_id,
                PartnerOrganization.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Partner organization not found"}), 404

        data, error = _parse_update_payload(row.name, current_user_id)
        if error:
            message, status = error
            return jsonify({"status": "error", "message": message}), status

        update_data = PartnerOrganizationUpdate(**data).model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(row, field, value)

        db.commit()
        db.refresh(row)
        return jsonify({
            "status": "success",
            "message": "Partner organization updated successfully",
            "data": PartnerOrganizationInDB.from_orm(row).dict(),
        })
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        db.close()


@partner_organizations_bp.route("/partner-organizations/<int:org_id>", methods=["DELETE"])
@jwt_required()
def delete_partner_organization(org_id):
    """Soft-delete a partner organization."""
    try:
        db = get_db()
        row = (
            db.query(PartnerOrganization)
            .filter(
                PartnerOrganization.id == org_id,
                PartnerOrganization.deleted_at.is_(None),
            )
            .first()
        )
        if not row:
            return jsonify({"status": "error", "message": "Partner organization not found"}), 404

        row.deleted_at = datetime.utcnow()
        row.updated_by = get_jwt_identity()
        db.commit()
        return jsonify({
            "status": "success",
            "message": "Partner organization deleted successfully",
        })
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        db.close()
