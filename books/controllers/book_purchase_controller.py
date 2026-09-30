"""
Book purchase: orders, payment reference + service provider, approval, paid editions, reader access.
"""

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import joinedload

from auth.models.models import User
from books.services.book_purchase_service import (
    BookPurchaseError,
    create_book_order,
    submit_book_order_payment,
    approve_book_payment,
    reject_book_payment,
    order_to_response,
    list_paid_editions_for_user,
    get_paid_edition_for_user,
    enrich_paid_edition,
    enrich_access_grant_with_lms_metadata,
    resolve_book_payment_method,
)
from books.services.entitlement_service import (
    user_has_admin_role,
    record_grant_log,
    mark_grant_revoked,
)
from books.models.sales_models import BookOrder
from books.models.schemas import BookAccessRequest
from database.db_connector import get_db
from services.lms_client import get_lms_client, LMSClientError
from config import public_storage_url

logger = logging.getLogger(__name__)

book_purchase_bp = Blueprint("book_purchase", __name__)


def _require_admin(db, user_id: int):
    if not user_has_admin_role(db, user_id):
        return jsonify({"status": "error", "message": "Admin access required"}), 403
    return None


def _target_user_for_paid_edition(db) -> tuple:
    """Return (subject_user_id, actor_user_id). Admins may pass ?user_id=."""
    actor_id = int(get_jwt_identity())
    subject_id = actor_id
    requested = request.args.get("user_id")
    if requested:
        if not user_has_admin_role(db, actor_id):
            raise PermissionError("Not authorized to manage access for other users")
        subject_id = int(requested)
    return subject_id, actor_id


def _require_paid_entitlement(db, user_id: int, edition_reference_id: str):
    ent = get_paid_edition_for_user(db, user_id, edition_reference_id)
    if not ent:
        return None, (jsonify({"status": "error", "message": "Edition not purchased"}), 403)
    return ent, None


def _issue_paid_edition_access(db, user: User, ent, edition_reference_id: str, ttl_seconds):
    client = get_lms_client()
    if not client:
        return None, (jsonify({"status": "error", "message": "LMS service not configured"}), 503)

    try:
        grant_data = client.grant_access_for_paid_edition(
            user_id=str(user.id),
            edition_reference_id=edition_reference_id,
            user_email=user.email,
            ttl_seconds=ttl_seconds,
        )
    except LMSClientError as exc:
        status = exc.status_code or 502
        if status == 409:
            return None, (jsonify({
                "status": "error",
                "message": "This book is not available for reading right now",
                "code": "book_unpublished",
            }), 409)
        details = exc.response_body if exc.response_body is not None else str(exc)
        return None, (jsonify({
            "status": "error",
            "message": "Failed to grant reading access",
            "details": details,
        }), 502 if status >= 500 else status)

    book_ref_for_log = (
        grant_data.get("edition_reference_id")
        or grant_data.get("book_reference_id")
        or ent.book_reference_id
    )
    record_grant_log(db, user.id, book_ref_for_log, grant_data)
    grant_data = enrich_access_grant_with_lms_metadata(
        grant_data,
        client,
        edition_reference_id,
        entitlement=ent,
    )
    return grant_data, None


def _payment_submission_body():
    """JSON body (same fields as application season payment)."""
    body = request.get_json(silent=True) or {}
    if not body and request.form:
        body = request.form.to_dict()
    return body


@book_purchase_bp.route("/book-orders", methods=["POST"])
@jwt_required()
def post_book_order():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        body = request.get_json(silent=True) or {}
        edition_ids = body.get("edition_reference_ids") or []
        if not edition_ids and body.get("items"):
            edition_ids = [i.get("edition_reference_id") for i in body["items"] if i.get("edition_reference_id")]

        client = get_lms_client()
        if not client:
            return jsonify({"status": "error", "message": "LMS service not configured"}), 503

        order = create_book_order(db, client, user_id, edition_ids)
        skipped = getattr(order, "_skipped_owned_editions", None)
        return jsonify({
            "status": "success",
            "data": order_to_response(order, include_skipped=skipped),
        }), 201
    except BookPurchaseError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    finally:
        db.close()


@book_purchase_bp.route("/book-orders", methods=["GET"])
@jwt_required()
def list_book_orders():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        is_admin = user_has_admin_role(db, user_id)
        query = db.query(BookOrder).options(
            joinedload(BookOrder.user),
            joinedload(BookOrder.payment),
            joinedload(BookOrder.items),
        )
        if not is_admin:
            query = query.filter(BookOrder.user_id == user_id)
        elif request.args.get("user_id"):
            query = query.filter(BookOrder.user_id == int(request.args.get("user_id")))

        orders = query.order_by(BookOrder.created_at.desc()).limit(100).all()
        return jsonify({
            "status": "success",
            "data": [order_to_response(o) for o in orders],
        })
    finally:
        db.close()


@book_purchase_bp.route("/book-orders/<int:order_id>", methods=["GET"])
@jwt_required()
def get_book_order(order_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        order = (
            db.query(BookOrder)
            .options(
                joinedload(BookOrder.user),
                joinedload(BookOrder.payment),
                joinedload(BookOrder.items),
            )
            .filter(BookOrder.id == order_id)
            .first()
        )
        if not order:
            return jsonify({"status": "error", "message": "Order not found"}), 404
        if order.user_id != user_id and not user_has_admin_role(db, user_id):
            return jsonify({"status": "error", "message": "Not authorized"}), 403

        data = order_to_response(order)
        if order.attachment_path:
            data["attachment_url"] = public_storage_url(order.attachment_path)
        return jsonify({"status": "success", "data": data})
    finally:
        db.close()


@book_purchase_bp.route("/book-orders/<int:order_id>/payment", methods=["POST"])
@jwt_required()
def submit_book_payment(order_id):
    """
    Submit payment for a book order using payment reference + service provider
    (same pattern as application payments — no receipt upload).
    """
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        body = _payment_submission_body()

        provider_raw = body.get("service_provider_id")
        if provider_raw is None:
            provider_raw = body.get("payment_method_id")
        service_provider_id = int(provider_raw) if provider_raw not in (None, "") else None

        payment_method = resolve_book_payment_method(
            db,
            body.get("payment_method"),
            service_provider_id,
        )

        payment_reference = (
            body.get("payment_reference")
            or body.get("bank_reference")
            or body.get("reference")
        )
        amount = body.get("amount")
        if amount is not None:
            amount = float(amount)
        mobile_number = body.get("mobile_number")
        description = body.get("description")

        payment = submit_book_order_payment(
            db,
            user_id,
            order_id,
            payment_method=payment_method,
            amount=amount,
            mobile_number=mobile_number,
            bank_reference=payment_reference,
            description=description,
        )

        return jsonify({
            "status": "success",
            "data": {
                "payment_id": payment.id,
                "transaction_id": payment.transaction_id,
                "payment_status": payment.payment_status.value,
                "amount": payment.amount,
                "payment_method": payment.payment_method,
                "payment_reference": payment.bank_reference,
                "mobile_number": payment.mobile_number,
                "order_id": order_id,
            },
        }), 201
    except BookPurchaseError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "message": f"Invalid payment payload: {exc}"}), 400
    finally:
        db.close()


@book_purchase_bp.route("/book-orders/payments/<int:payment_id>/approve", methods=["POST"])
@jwt_required()
def approve_payment(payment_id):
    db = get_db()
    try:
        admin_id = int(get_jwt_identity())
        denied = _require_admin(db, admin_id)
        if denied:
            return denied

        result = approve_book_payment(db, payment_id, admin_id)
        return jsonify({"status": "success", "data": result})
    except BookPurchaseError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    finally:
        db.close()


@book_purchase_bp.route("/book-orders/payments/<int:payment_id>/reject", methods=["POST"])
@jwt_required()
def reject_payment(payment_id):
    db = get_db()
    try:
        admin_id = int(get_jwt_identity())
        denied = _require_admin(db, admin_id)
        if denied:
            return denied

        body = request.get_json(silent=True) or {}
        result = reject_book_payment(db, payment_id, admin_id, body.get("reason"))
        return jsonify({"status": "success", "data": result})
    except BookPurchaseError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    finally:
        db.close()


@book_purchase_bp.route("/my/paid-editions", methods=["GET"])
@book_purchase_bp.route("/my/books", methods=["GET"])
@jwt_required()
def my_paid_editions():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        client = get_lms_client()
        rows = list_paid_editions_for_user(db, user_id)
        return jsonify({
            "status": "success",
            "data": [enrich_paid_edition(row, client) for row in rows],
        })
    finally:
        db.close()


@book_purchase_bp.route("/my/paid-editions/<edition_reference_id>", methods=["GET"])
@jwt_required()
def get_my_paid_edition(edition_reference_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        ent = get_paid_edition_for_user(db, user_id, edition_reference_id)
        if not ent:
            return jsonify({"status": "error", "message": "Edition not purchased"}), 403

        client = get_lms_client()
        return jsonify({
            "status": "success",
            "data": enrich_paid_edition(ent, client),
        })
    finally:
        db.close()


@book_purchase_bp.route("/my/paid-editions/<edition_reference_id>/access/status", methods=["GET"])
@jwt_required()
def paid_edition_access_status(edition_reference_id):
    """LMS active access status for a purchased edition."""
    db = get_db()
    try:
        try:
            subject_id, _ = _target_user_for_paid_edition(db)
        except PermissionError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 403

        _, denied = _require_paid_entitlement(db, subject_id, edition_reference_id)
        if denied:
            return denied

        client = get_lms_client()
        if not client:
            return jsonify({"status": "error", "message": "LMS service not configured"}), 503

        data = client.get_access_status_for_paid_edition(str(subject_id), edition_reference_id)
        return jsonify({"status": "success", "data": data})
    except LMSClientError as exc:
        details = exc.response_body if exc.response_body is not None else str(exc)
        return jsonify({
            "status": "error",
            "message": "Failed to check reading access status",
            "details": details,
        }), exc.status_code or 502
    finally:
        db.close()


@book_purchase_bp.route("/my/paid-editions/<edition_reference_id>/access", methods=["DELETE"])
@jwt_required()
def revoke_paid_edition_access(edition_reference_id):
    """Revoke active LMS reading session for a purchased edition."""
    db = get_db()
    try:
        try:
            subject_id, _ = _target_user_for_paid_edition(db)
        except PermissionError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 403

        ent, denied = _require_paid_entitlement(db, subject_id, edition_reference_id)
        if denied:
            return denied

        client = get_lms_client()
        if not client:
            return jsonify({"status": "error", "message": "LMS service not configured"}), 503

        try:
            result = client.revoke_access_for_paid_edition(str(subject_id), edition_reference_id)
        except LMSClientError as exc:
            details = exc.response_body if exc.response_body is not None else str(exc)
            return jsonify({
                "status": "error",
                "message": "Failed to revoke reading access",
                "details": details,
            }), exc.status_code or 502

        mark_grant_revoked(db, subject_id, edition_reference_id)
        if ent.book_reference_id and str(ent.book_reference_id) != str(edition_reference_id):
            mark_grant_revoked(db, subject_id, ent.book_reference_id)

        return jsonify({
            "status": "success",
            "message": "Reading access revoked",
            "data": result,
        })
    finally:
        db.close()


@book_purchase_bp.route("/my/paid-editions/<edition_reference_id>/access/reissue", methods=["POST"])
@jwt_required()
def reissue_paid_edition_access(edition_reference_id):
    """Revoke any active LMS token, then issue a fresh reading session."""
    db = get_db()
    try:
        try:
            subject_id, _ = _target_user_for_paid_edition(db)
        except PermissionError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 403

        ent, denied = _require_paid_entitlement(db, subject_id, edition_reference_id)
        if denied:
            return denied

        user = db.query(User).get(subject_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        client = get_lms_client()
        if client:
            try:
                client.revoke_access_for_paid_edition(str(subject_id), edition_reference_id)
            except LMSClientError:
                pass
            mark_grant_revoked(db, subject_id, edition_reference_id)

        payload = request.get_json(silent=True) or {}
        access_request = BookAccessRequest(**payload)
        grant_data, err = _issue_paid_edition_access(
            db,
            user,
            ent,
            edition_reference_id,
            access_request.ttl_seconds,
        )
        if err:
            return err

        return jsonify({
            "status": "success",
            "message": "Reading access re-issued",
            "data": grant_data,
        })
    except Exception as exc:
        logger.error("reissue_paid_edition_access: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@book_purchase_bp.route("/my/paid-editions/<edition_reference_id>/access", methods=["POST"])
@jwt_required()
def grant_paid_edition_access(edition_reference_id):
    """LMS reading token — only after approved purchase (issue or refresh)."""
    db = get_db()
    try:
        try:
            subject_id, _ = _target_user_for_paid_edition(db)
        except PermissionError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 403

        ent, denied = _require_paid_entitlement(db, subject_id, edition_reference_id)
        if denied:
            return denied

        user = db.query(User).get(subject_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        payload = request.get_json(silent=True) or {}
        access_request = BookAccessRequest(**payload)
        grant_data, err = _issue_paid_edition_access(
            db,
            user,
            ent,
            edition_reference_id,
            access_request.ttl_seconds,
        )
        if err:
            return err

        return jsonify({"status": "success", "data": grant_data})
    except Exception as exc:
        logger.error("grant_paid_edition_access: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()
