"""
Book sales: edition pricing, listings, store catalog, and customer price resolution.
"""

import logging
import os
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from books.models.sales_models import BookListing, BookOrder, BookOrderStatus, ListingStatus
from books.models.sales_schemas import (
    EditionPriceCreate,
    ListingStatusUpdate,
    BookOrderCreate,
)
from books.services.entitlement_service import user_has_admin_role
from books.services.listing_service import (
    ListingValidationError,
    get_listing,
    list_edition,
    unlist_edition,
    list_listed_editions,
    listing_to_response,
)
from books.services.pricing_service import create_edition_price, get_active_edition_price, price_to_response
from books.services.price_resolution_service import (
    resolve_customer_price,
    build_store_edition_payload,
    attach_store_user_pricing,
    load_user_paid_purchase_sets,
    PriceResolutionError,
)
from books.services.lms_edition_helpers import attach_store_catalog_metadata, book_reference_id
from books.services.store_visibility_service import (
    filter_store_rows_for_visibility,
    is_edition_visible_in_store,
    listed_edition_refs_for_book,
    pick_current_edition_reference,
)
from books.services.order_service import create_book_order, order_to_response, OrderServiceError
from database.db_connector import get_db
from services.lms_client import get_lms_client, LMSClientError

logger = logging.getLogger(__name__)

book_sales_bp = Blueprint("book_sales", __name__)


def _require_admin(db, user_id: int):
    if not user_has_admin_role(db, user_id):
        return jsonify({"status": "error", "message": "Admin access required"}), 403
    return None


def _lms_config_hint() -> dict:
    missing = []
    if not os.getenv("LMS_BASE_URL"):
        missing.append("LMS_BASE_URL")
    if not os.getenv("LMS_CLIENT_ID"):
        missing.append("LMS_CLIENT_ID")
    if not os.getenv("LMS_CLIENT_SECRET"):
        missing.append("LMS_CLIENT_SECRET")
    return {"missing_env": missing} if missing else {}


def _lms_unavailable():
    body = {
        "status": "error",
        "message": "LMS service not configured",
    }
    hint = _lms_config_hint()
    if hint:
        body["details"] = hint
        body["message"] = (
            "LMS service not configured on this server. "
            "Set LMS_BASE_URL, LMS_CLIENT_ID, and LMS_CLIENT_SECRET, then restart the API."
        )
    return jsonify(body), 503


# --- Edition pricing (admin) ---


@book_sales_bp.route("/book-editions/<edition_reference_id>/price", methods=["POST"])
@jwt_required()
def set_edition_price(edition_reference_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        payload = EditionPriceCreate(**(request.get_json() or {}))
        require_lms = request.args.get("validate_lms", "false").lower() in ("1", "true", "yes")
        client = get_lms_client()
        if client:
            try:
                client.get_edition(edition_reference_id)
            except LMSClientError as exc:
                if exc.status_code == 404:
                    return jsonify({"status": "error", "message": "Edition not found in LMS"}), 404
                err = {"status": "error", "message": str(exc) or "Failed to validate edition with LMS"}
                if exc.response_body is not None:
                    err["lms"] = exc.response_body
                return jsonify(err), exc.status_code or 502
        elif require_lms:
            return _lms_unavailable()
        else:
            logger.info(
                "Saving edition price for %s without LMS validation (LMS not configured on server)",
                edition_reference_id,
            )

        price = create_edition_price(
            db,
            edition_reference_id,
            payload.new_buyer_price,
            payload.previous_buyer_price,
            payload.currency.upper(),
            user_id,
        )
        return jsonify({"status": "success", "data": price_to_response(price)}), 201
    except Exception as exc:
        db.rollback()
        logger.error("set_edition_price: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@book_sales_bp.route("/book-editions/<edition_reference_id>/price", methods=["GET"])
@jwt_required()
def get_edition_price(edition_reference_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        price = get_active_edition_price(db, edition_reference_id)
        if not price:
            return jsonify({"status": "error", "message": "No active price for this edition"}), 404
        return jsonify({"status": "success", "data": price_to_response(price)})
    finally:
        db.close()


# --- Listings (admin) ---


@book_sales_bp.route("/book-editions/<edition_reference_id>/listing", methods=["POST"])
@jwt_required()
def create_edition_listing(edition_reference_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        client = get_lms_client()
        if not client:
            return _lms_unavailable()

        listing = list_edition(db, client, edition_reference_id, user_id)
        return jsonify({"status": "success", "data": listing_to_response(listing)}), 201
    except ListingValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    except Exception as exc:
        db.rollback()
        logger.error("create_edition_listing: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@book_sales_bp.route("/book-editions/<edition_reference_id>/listing", methods=["DELETE", "PATCH"])
@jwt_required()
def update_edition_listing(edition_reference_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        if request.method == "PATCH":
            body = ListingStatusUpdate(**(request.get_json() or {}))
            if body.status != ListingStatus.UNLISTED.value:
                return jsonify({"status": "error", "message": "Use POST to list an edition"}), 400

        listing = unlist_edition(db, edition_reference_id, user_id)
        return jsonify({"status": "success", "data": listing_to_response(listing)})
    except ListingValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    finally:
        db.close()


@book_sales_bp.route("/listings", methods=["GET"])
@jwt_required()
def get_listings():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        status_filter = request.args.get("status")
        query = db.query(BookListing)
        if status_filter:
            query = query.filter(BookListing.status == status_filter.upper())
        listings = query.order_by(BookListing.updated_at.desc()).all()

        data = []
        for listing in listings:
            item = listing_to_response(listing)
            price = get_active_edition_price(db, listing.edition_reference_id)
            if price:
                item["new_buyer_price"] = float(price.new_buyer_price)
                item["previous_buyer_price"] = float(price.previous_buyer_price)
                item["currency"] = price.currency
            data.append(item)

        return jsonify({"status": "success", "data": data})
    finally:
        db.close()


@book_sales_bp.route("/listings/<int:listing_id>", methods=["PATCH", "DELETE"])
@jwt_required()
def update_listing_by_id(listing_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        listing = db.query(BookListing).get(listing_id)
        if not listing:
            return jsonify({"status": "error", "message": "Listing not found"}), 404

        if request.method == "PATCH":
            body = ListingStatusUpdate(**(request.get_json() or {}))
            if body.status == ListingStatus.LISTED.value:
                client = get_lms_client()
                if not client:
                    return _lms_unavailable()
                listing = list_edition(db, client, listing.edition_reference_id, user_id)
            else:
                listing = unlist_edition(db, listing.edition_reference_id, user_id)
        else:
            listing = unlist_edition(db, listing.edition_reference_id, user_id)

        return jsonify({"status": "success", "data": listing_to_response(listing)})
    except ListingValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    finally:
        db.close()


# --- Store (public catalog + authenticated pricing) ---


@book_sales_bp.route("/store/books", methods=["GET"])
@jwt_required(optional=True)
def store_list_books():
    """Listed editions with prices and LMS metadata; user-specific price when JWT sent."""
    db = get_db()
    try:
        identity = get_jwt_identity()
        user_id = int(identity) if identity is not None else None
        owned_editions: set = set()
        owned_books: set = set()
        owned_by_book: dict = {}
        if user_id is not None:
            owned_editions, owned_books, owned_by_book = load_user_paid_purchase_sets(db, user_id)

        listings = list_listed_editions(db)
        client = get_lms_client()
        edition_index = {}
        if client:
            try:
                edition_index = client.build_edition_index(published_only=False)
            except LMSClientError:
                edition_index = {}

        data = []
        for listing in listings:
            payload = build_store_edition_payload(db, listing)
            if payload:
                edition = edition_index.get(listing.edition_reference_id)
                row = attach_store_catalog_metadata(payload, edition, client)
                row = attach_store_user_pricing(
                    row,
                    user_id,
                    owned_editions=owned_editions,
                    owned_books=owned_books,
                    edition_lms=edition,
                )
                data.append(row)

        data = filter_store_rows_for_visibility(
            data,
            edition_index,
            owned_editions,
            owned_by_book,
        )

        body = {"status": "success", "data": data}
        body["meta"] = {
            "authenticated": user_id is not None,
            "store_edition_policy": (
                "OWNED_AND_CURRENT_FOR_RETURNING_BUYERS"
                if user_id is not None and owned_books
                else "CURRENT_EDITION_ONLY"
            ),
        }
        if user_id is not None:
            body["meta"]["user_owned_edition_ids"] = sorted(owned_editions)
        return jsonify(body)
    finally:
        db.close()


@book_sales_bp.route("/store/books/<edition_reference_id>", methods=["GET"])
@jwt_required(optional=True)
def store_get_book(edition_reference_id):
    db = get_db()
    try:
        listing = get_listing(db, edition_reference_id)
        if not listing or listing.status != ListingStatus.LISTED.value:
            return jsonify({"status": "error", "message": "Edition is not listed for sale"}), 404

        payload = build_store_edition_payload(db, listing)
        if not payload:
            return jsonify({"status": "error", "message": "No active price for this edition"}), 409

        identity = get_jwt_identity()
        user_id = int(identity) if identity is not None else None
        owned_editions: set = set()
        owned_by_book: dict = {}
        if user_id is not None:
            owned_editions, _, owned_by_book = load_user_paid_purchase_sets(db, user_id)

        client = get_lms_client()
        edition_index: dict = {}
        edition = None
        if client:
            try:
                edition_index = client.build_edition_index(published_only=False)
            except LMSClientError:
                edition_index = {}
            edition = edition_index.get(edition_reference_id)
            if edition is None:
                try:
                    edition = client.get_edition(edition_reference_id)
                except LMSClientError:
                    edition = None

        book_ref = book_reference_id(edition) if edition else None
        listed_for_book: list = []
        current_ref = None

        if book_ref:
            all_listed_refs = [lst.edition_reference_id for lst in list_listed_editions(db)]
            listed_for_book = listed_edition_refs_for_book(book_ref, all_listed_refs, edition_index)
            if not is_edition_visible_in_store(
                edition_reference_id,
                book_ref,
                listed_for_book,
                edition_index,
                owned_by_book,
            ):
                return jsonify({
                    "status": "error",
                    "message": "This edition is not shown in the store for your account. Open the current or your owned edition from the catalog.",
                }), 404
            current_ref = pick_current_edition_reference(listed_for_book, edition_index)

        row = attach_store_catalog_metadata(payload, edition, client)
        row = attach_store_user_pricing(
            row,
            user_id,
            owned_editions=owned_editions,
            owned_books=set(owned_by_book.keys()),
            edition_lms=edition,
        )
        ref = str(edition_reference_id)
        owns = ref in owned_editions
        is_current = bool(current_ref and ref == current_ref)
        row["is_current_edition"] = is_current if book_ref else None
        if book_ref:
            row["edition_display_role"] = (
                "OWNED_CURRENT" if owns and is_current else ("OWNED" if owns else "CURRENT")
            )
        else:
            row["edition_display_role"] = "CURRENT"
        row["show_in_store"] = True
        return jsonify({"status": "success", "data": row})
    finally:
        db.close()


@book_sales_bp.route("/store/books/<edition_reference_id>/price", methods=["GET"])
@jwt_required()
def store_customer_price(edition_reference_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        client = get_lms_client()
        if not client:
            return _lms_unavailable()

        data = resolve_customer_price(db, client, user_id, edition_reference_id)
        return jsonify({
            "status": "success",
            "data": {
                "edition_reference_id": data["edition_reference_id"],
                "customer_type": data["customer_type"],
                "price": data["price"],
                "currency": data["currency"],
            },
        })
    except PriceResolutionError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    finally:
        db.close()


# --- Orders & purchase history ---


@book_sales_bp.route("/orders", methods=["POST"])
@jwt_required()
def create_order():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        body = BookOrderCreate(**(request.get_json() or {}))
        client = get_lms_client()
        if not client:
            return _lms_unavailable()

        edition_refs = [item.edition_reference_id for item in body.items]
        quantities = [item.quantity for item in body.items]
        order = create_book_order(
            db,
            client,
            user_id,
            edition_refs,
            quantities,
            mark_completed=False,
        )
        return jsonify({"status": "success", "data": order_to_response(order)}), 201
    except OrderServiceError as exc:
        return jsonify({"status": "error", "message": str(exc)}), exc.status_code
    except Exception as exc:
        db.rollback()
        logger.error("create_order: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@book_sales_bp.route("/orders", methods=["GET"])
@jwt_required()
def list_orders():
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        is_admin = user_has_admin_role(db, user_id)

        query = db.query(BookOrder)
        if not is_admin:
            query = query.filter(BookOrder.user_id == user_id)
        elif request.args.get("user_id"):
            query = query.filter(BookOrder.user_id == int(request.args.get("user_id")))

        orders = query.order_by(BookOrder.created_at.desc()).limit(100).all()
        return jsonify({
            "status": "success",
            "data": [order_to_response(order) for order in orders],
        })
    finally:
        db.close()


@book_sales_bp.route("/orders/<int:order_id>", methods=["PATCH"])
@jwt_required()
def update_order_status(order_id):
    """Mark order completed (admin) — wire to payment confirmation in production."""
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        denied = _require_admin(db, user_id)
        if denied:
            return denied

        order = db.query(BookOrder).get(order_id)
        if not order:
            return jsonify({"status": "error", "message": "Order not found"}), 404

        body = request.get_json(silent=True) or {}
        new_status = (body.get("status") or "").lower()
        if new_status == BookOrderStatus.completed.value:
            order.status = BookOrderStatus.completed.value
            order.completed_at = datetime.utcnow()
        elif new_status in {s.value for s in BookOrderStatus}:
            order.status = new_status
            if new_status != BookOrderStatus.completed.value:
                order.completed_at = None
        else:
            return jsonify({"status": "error", "message": "Invalid status"}), 400

        db.commit()
        db.refresh(order)
        return jsonify({"status": "success", "data": order_to_response(order)})
    finally:
        db.close()


@book_sales_bp.route("/orders/<int:order_id>", methods=["GET"])
@jwt_required()
def get_order(order_id):
    db = get_db()
    try:
        user_id = int(get_jwt_identity())
        order = db.query(BookOrder).get(order_id)
        if not order:
            return jsonify({"status": "error", "message": "Order not found"}), 404
        if order.user_id != user_id and not user_has_admin_role(db, user_id):
            return jsonify({"status": "error", "message": "Not authorized"}), 403
        return jsonify({"status": "success", "data": order_to_response(order)})
    finally:
        db.close()


@book_sales_bp.route("/purchases", methods=["GET"])
@jwt_required()
def list_purchases():
    """Paid editions (approved payments only). Prefer GET /api/my/paid-editions."""
    db = get_db()
    try:
        from books.services.book_purchase_service import list_paid_editions_for_user, enrich_paid_edition

        user_id = int(get_jwt_identity())
        is_admin = user_has_admin_role(db, user_id)
        target_user_id = user_id
        if is_admin and request.args.get("user_id"):
            target_user_id = int(request.args.get("user_id"))

        client = get_lms_client()
        rows = list_paid_editions_for_user(db, target_user_id)
        return jsonify({
            "status": "success",
            "data": [enrich_paid_edition(row, client) for row in rows],
        })
    finally:
        db.close()
