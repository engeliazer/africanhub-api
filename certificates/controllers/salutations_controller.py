from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from certificates.models.models import Salutation
from certificates.models.schemas import salutation_payload
from database.db_connector import get_db

salutations_bp = Blueprint("salutations", __name__)


@salutations_bp.route("/salutations", methods=["GET"])
@jwt_required()
def list_salutations():
    """List active salutations for participant roster forms."""
    db = get_db()
    try:
        rows = (
            db.query(Salutation)
            .filter(Salutation.is_active == True)
            .order_by(Salutation.display_order.asc(), Salutation.label.asc())
            .all()
        )
        return jsonify({
            "status": "success",
            "data": [salutation_payload(row) for row in rows],
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()
