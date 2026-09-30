"""
Books management and reading access via the external LMS.

User-facing endpoints issue content tokens after local entitlement checks.
Admin endpoints manage book-to-subject links used for enrollment validation.
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from auth.models.models import User
from books.models.models import BookSubjectLink, BookAccessGrantLog
from books.models.schemas import (
    BookSubjectLinkCreate,
    BookSubjectLinkUpdate,
    BookSubjectLinkInDB,
    BookAccessRequest,
)
from books.services.entitlement_service import (
    check_book_access_entitlement,
    record_grant_log,
    mark_grant_revoked,
    user_has_admin_role,
)
from database.db_connector import get_db
from services.lms_client import get_lms_client, LMSClientError
from subjects.models.models import Subject

logger = logging.getLogger(__name__)

books_bp = Blueprint("books", __name__)


def _lms_unavailable_response():
    return jsonify({
        "status": "error",
        "message": "LMS service not configured",
        "details": "Set LMS_BASE_URL, LMS_CLIENT_ID, and LMS_CLIENT_SECRET in environment variables",
    }), 503


def _merge_catalog_with_links(db, books):
    links = (
        db.query(BookSubjectLink, Subject.name)
        .join(Subject, Subject.id == BookSubjectLink.subject_id)
        .filter(
            BookSubjectLink.deleted_at.is_(None),
            BookSubjectLink.is_active.is_(True),
        )
        .all()
    )
    link_by_book = {link.lms_book_id: (link, subject_name) for link, subject_name in links}

    merged = []
    for book in books:
        book_id = book.get("id") or book.get("book_id")
        if book_id is None:
            continue
        item = dict(book)
        item["id"] = book_id
        link_info = link_by_book.get(book_id)
        if link_info:
            link, subject_name = link_info
            item["subject_id"] = link.subject_id
            item["subject_name"] = subject_name
            item["is_linked"] = True
        else:
            item["subject_id"] = None
            item["subject_name"] = None
            item["is_linked"] = False
        merged.append(item)
    return merged


@books_bp.route("/books", methods=["GET"])
@jwt_required()
def list_books():
    """List published books from the LMS catalog, enriched with local subject links."""
    db = get_db()
    try:
        client = get_lms_client()
        if not client:
            return _lms_unavailable_response()

        published_only = request.args.get("published_only", "true").lower() != "false"
        books = client.list_books(published_only=published_only)
        data = _merge_catalog_with_links(db, books)

        return jsonify({"status": "success", "data": data})
    except LMSClientError as exc:
        logger.error("Failed to list LMS books: %s", exc)
        return jsonify({
            "status": "error",
            "message": "Failed to fetch book catalog",
            "details": str(exc),
        }), exc.status_code or 502
    except Exception as exc:
        logger.error("Unexpected error listing books: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/<int:book_id>/access", methods=["POST"])
@jwt_required()
def grant_book_access(book_id):
    """
    Grant a reading-session content token after entitlement checks.

    Returns the LMS access token and reader URLs for the client to use directly.
    """
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        user = db.query(User).get(current_user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        allowed, reason = check_book_access_entitlement(db, user, book_id)
        if not allowed:
            return jsonify({"status": "error", "message": reason}), 403

        payload = request.get_json(silent=True) or {}
        access_request = BookAccessRequest(**payload)

        client = get_lms_client()
        if not client:
            return _lms_unavailable_response()

        grant_data = client.grant_access_token(
            user_id=str(user.id),
            book_reference_id=str(book_id),
            user_email=user.email,
            ttl_seconds=access_request.ttl_seconds,
        )

        record_grant_log(db, user.id, book_id, grant_data)

        return jsonify({"status": "success", "data": grant_data})
    except LMSClientError as exc:
        if exc.status_code == 409:
            return jsonify({
                "status": "error",
                "message": "This book is not available right now",
                "code": "book_unpublished",
            }), 409
        if exc.status_code == 401:
            return jsonify({
                "status": "error",
                "message": "LMS authentication failed",
            }), 502
        logger.error("Failed to grant book access for book %s: %s", book_id, exc)
        return jsonify({
            "status": "error",
            "message": "Failed to grant book access",
            "details": str(exc),
        }), exc.status_code or 502
    except Exception as exc:
        logger.error("Unexpected error granting book access: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/<int:book_id>/access/status", methods=["GET"])
@jwt_required()
def get_book_access_status(book_id):
    """Check whether the current user has active LMS access for a book."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        user = db.query(User).get(current_user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        client = get_lms_client()
        if not client:
            return _lms_unavailable_response()

        status_data = client.get_access_status(str(user.id), str(book_id))
        return jsonify({"status": "success", "data": status_data})
    except LMSClientError as exc:
        logger.error("Failed to get access status for book %s: %s", book_id, exc)
        return jsonify({
            "status": "error",
            "message": "Failed to check book access status",
            "details": str(exc),
        }), exc.status_code or 502
    except Exception as exc:
        logger.error("Unexpected error checking book access status: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/<int:book_id>/access", methods=["DELETE"])
@jwt_required()
def revoke_book_access(book_id):
    """Revoke active LMS access for the current user (or any user if admin)."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        actor = db.query(User).get(current_user_id)
        if not actor:
            return jsonify({"status": "error", "message": "User not found"}), 404

        target_user_id = current_user_id
        if user_has_admin_role(db, current_user_id):
            requested_user_id = request.args.get("user_id")
            if requested_user_id:
                target_user_id = int(requested_user_id)
        elif request.args.get("user_id"):
            return jsonify({"status": "error", "message": "Not authorized to revoke access for other users"}), 403

        client = get_lms_client()
        if not client:
            return _lms_unavailable_response()

        client.revoke_active_access(str(target_user_id), str(book_id))
        mark_grant_revoked(db, target_user_id, book_id)

        return jsonify({
            "status": "success",
            "message": "Book access revoked",
            "data": {"user_id": target_user_id, "book_id": book_id},
        })
    except LMSClientError as exc:
        logger.error("Failed to revoke access for book %s: %s", book_id, exc)
        return jsonify({
            "status": "error",
            "message": "Failed to revoke book access",
            "details": str(exc),
        }), exc.status_code or 502
    except Exception as exc:
        logger.error("Unexpected error revoking book access: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/access/grants", methods=["GET"])
@jwt_required()
def list_book_access_grants():
    """List access grants — users see their own; admins can filter by user_id/book_id."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        is_admin = user_has_admin_role(db, current_user_id)

        user_id = request.args.get("user_id")
        book_id = request.args.get("book_id", type=int)

        if is_admin:
            query = db.query(BookAccessGrantLog)
            if user_id:
                query = query.filter(BookAccessGrantLog.user_id == int(user_id))
            if book_id is not None:
                query = query.filter(BookAccessGrantLog.lms_book_id == book_id)
        else:
            query = db.query(BookAccessGrantLog).filter(BookAccessGrantLog.user_id == current_user_id)
            if book_id is not None:
                query = query.filter(BookAccessGrantLog.lms_book_id == book_id)

        logs = query.order_by(BookAccessGrantLog.created_at.desc()).limit(100).all()
        return jsonify({
            "status": "success",
            "data": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "lms_book_id": log.lms_book_id,
                    "lms_grant_id": log.lms_grant_id,
                    "status": log.status,
                    "issued_at": log.issued_at.isoformat() if log.issued_at else None,
                    "expires_at": log.expires_at.isoformat() if log.expires_at else None,
                    "revoked_at": log.revoked_at.isoformat() if log.revoked_at else None,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        })
    except Exception as exc:
        logger.error("Unexpected error listing grant logs: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/links", methods=["GET"])
@jwt_required()
def list_book_links():
    """List local book-to-subject links (admin only)."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        if not user_has_admin_role(db, current_user_id):
            return jsonify({"status": "error", "message": "Admin access required"}), 403

        links = (
            db.query(BookSubjectLink, Subject.name)
            .join(Subject, Subject.id == BookSubjectLink.subject_id)
            .filter(BookSubjectLink.deleted_at.is_(None))
            .order_by(BookSubjectLink.created_at.desc())
            .all()
        )

        data = []
        for link, subject_name in links:
            item = BookSubjectLinkInDB.from_orm(link).dict()
            item["subject_name"] = subject_name
            data.append(item)

        return jsonify({"status": "success", "data": data})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/links", methods=["POST"])
@jwt_required()
def create_book_link():
    """Link an LMS book to a local subject for entitlement checks (admin only)."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        if not user_has_admin_role(db, current_user_id):
            return jsonify({"status": "error", "message": "Admin access required"}), 403

        payload = BookSubjectLinkCreate(**(request.get_json() or {}))

        subject = db.query(Subject).get(payload.subject_id)
        if not subject:
            return jsonify({"status": "error", "message": "Subject not found"}), 404

        existing = (
            db.query(BookSubjectLink)
            .filter(
                BookSubjectLink.lms_book_id == payload.lms_book_id,
                BookSubjectLink.subject_id == payload.subject_id,
                BookSubjectLink.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            return jsonify({"status": "error", "message": "This book is already linked to the subject"}), 409

        link = BookSubjectLink(
            lms_book_id=payload.lms_book_id,
            subject_id=payload.subject_id,
            title=payload.title,
            description=payload.description,
            created_by=current_user_id,
            updated_by=current_user_id,
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        return jsonify({
            "status": "success",
            "data": BookSubjectLinkInDB.from_orm(link).dict(),
        }), 201
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/links/<int:link_id>", methods=["PUT"])
@jwt_required()
def update_book_link(link_id):
    """Update a book-to-subject link (admin only)."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        if not user_has_admin_role(db, current_user_id):
            return jsonify({"status": "error", "message": "Admin access required"}), 403

        link = db.query(BookSubjectLink).filter(
            BookSubjectLink.id == link_id,
            BookSubjectLink.deleted_at.is_(None),
        ).first()
        if not link:
            return jsonify({"status": "error", "message": "Book link not found"}), 404

        payload = BookSubjectLinkUpdate(**(request.get_json() or {}))
        update_data = payload.dict(exclude_unset=True)

        if "subject_id" in update_data:
            subject = db.query(Subject).get(update_data["subject_id"])
            if not subject:
                return jsonify({"status": "error", "message": "Subject not found"}), 404

        for field, value in update_data.items():
            setattr(link, field, value)
        link.updated_by = current_user_id
        db.commit()
        db.refresh(link)

        return jsonify({
            "status": "success",
            "data": BookSubjectLinkInDB.from_orm(link).dict(),
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/links/<int:link_id>", methods=["DELETE"])
@jwt_required()
def delete_book_link(link_id):
    """Soft-delete a book-to-subject link (admin only)."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        if not user_has_admin_role(db, current_user_id):
            return jsonify({"status": "error", "message": "Admin access required"}), 403

        link = db.query(BookSubjectLink).filter(
            BookSubjectLink.id == link_id,
            BookSubjectLink.deleted_at.is_(None),
        ).first()
        if not link:
            return jsonify({"status": "error", "message": "Book link not found"}), 404

        link.deleted_at = datetime.utcnow()
        link.is_active = False
        link.updated_by = current_user_id
        db.commit()

        return jsonify({"status": "success", "message": "Book link removed"})
    except Exception as exc:
        db.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/books/my", methods=["GET"])
@jwt_required()
def list_my_books():
    """List books the current user is entitled to read based on paid enrollments."""
    db = get_db()
    try:
        current_user_id = int(get_jwt_identity())
        user = db.query(User).get(current_user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        client = get_lms_client()
        if not client:
            return _lms_unavailable_response()

        all_books = client.list_books(published_only=True)
        merged = _merge_catalog_with_links(db, all_books)

        if user_has_admin_role(db, current_user_id):
            entitled = merged
        else:
            entitled = []
            for book in merged:
                book_id = book.get("id")
                if book_id is None:
                    continue
                allowed, _ = check_book_access_entitlement(db, user, book_id)
                if allowed:
                    entitled.append(book)

        return jsonify({"status": "success", "data": entitled})
    except LMSClientError as exc:
        logger.error("Failed to list entitled books: %s", exc)
        return jsonify({
            "status": "error",
            "message": "Failed to fetch books",
            "details": str(exc),
        }), exc.status_code or 502
    except Exception as exc:
        logger.error("Unexpected error listing my books: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        db.close()


@books_bp.route("/health/lms", methods=["GET"])
def check_lms_health():
    """Health check for LMS integration."""
    import time

    client = get_lms_client()
    if not client:
        return jsonify({
            "status": "unhealthy",
            "lms_api": "not_configured",
            "message": "LMS credentials not set in environment variables",
        }), 503

    start = time.time()
    if client.test_connection():
        return jsonify({
            "status": "healthy",
            "lms_api": "reachable",
            "response_time_ms": round((time.time() - start) * 1000, 2),
        }), 200

    return jsonify({
        "status": "degraded",
        "lms_api": "unreachable",
    }), 503
