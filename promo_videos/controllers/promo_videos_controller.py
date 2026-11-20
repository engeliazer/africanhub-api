"""Admin CRUD and public playback for promotional VdoCipher videos."""

import logging
import os
import re
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from database.db_connector import get_db
from promo_videos.controllers.cover_utils import save_promo_cover
from promo_videos.models.models import PromoVideo
from promo_videos.models.schemas import PromoVideoCreate, PromoVideoUpdate
from services.vdocipher_service import VdoCipherService

logger = logging.getLogger(__name__)
promo_videos_bp = Blueprint("promo_videos", __name__)

PUBLICATION_STATUSES = {"draft", "published"}
VIDEO_STATUSES = {"pending", "processing", "ready", "failed"}

_promo_vdocipher_service = None


def get_promo_vdocipher_service():
    """Lazy client bound to the restricted promo key. Never falls back to the main secret."""
    global _promo_vdocipher_service
    if _promo_vdocipher_service is not None:
        return _promo_vdocipher_service
    secret = os.getenv("VDOCIPHER_PROMO_API_SECRET")
    if not secret:
        return None
    _promo_vdocipher_service = VdoCipherService(api_secret=secret)
    return _promo_vdocipher_service


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug[:200]


def unique_slug(db, base: str, exclude_id=None) -> str:
    """Pick a slug that does not collide, including soft-deleted rows (the column is unique)."""
    candidate = base or "video"
    suffix = 2
    while True:
        query = db.query(PromoVideo).filter(PromoVideo.slug == candidate)
        if exclude_id is not None:
            query = query.filter(PromoVideo.id != exclude_id)
        if query.first() is None:
            return candidate
        candidate = f"{(base or 'video')[:190]}-{suffix}"
        suffix += 1


def map_video_status(raw) -> str:
    value = (raw or "").strip().lower()
    if value == "ready":
        return "ready"
    if value in {"failed", "error"}:
        return "failed"
    if value in {"processing", "queued", "queue", "pre-upload", "preupload"}:
        return "processing"
    return "pending"


def _iso(value):
    return value.isoformat() if value else None


def serialize_admin(video: PromoVideo) -> dict:
    return {
        "id": video.id,
        "title": video.title,
        "slug": video.slug,
        "description": video.description,
        "status": video.status,
        "video_status": video.video_status,
        "vdocipher_video_id": video.vdocipher_video_id,
        "thumbnail_url": video.thumbnail_url,
        "cover_url": video.cover_url,
        "video_duration": video.video_duration,
        "sort_order": video.sort_order,
        "created_by": video.created_by,
        "updated_by": video.updated_by,
        "created_at": _iso(video.created_at),
        "updated_at": _iso(video.updated_at),
    }


def serialize_public(video: PromoVideo) -> dict:
    duration = video.video_duration
    return {
        "id": video.id,
        "title": video.title,
        "slug": video.slug,
        "description": video.description,
        "video_status": video.video_status,
        "thumbnail_url": video.thumbnail_url,
        "cover_url": video.cover_url,
        "video_duration": int(duration) if duration else 0,
        "sort_order": video.sort_order,
    }


def _active_query(db):
    return db.query(PromoVideo).filter(PromoVideo.deleted_at.is_(None))


def _apply_vdocipher_details(video: PromoVideo, details: dict, keep_thumbnail: bool) -> None:
    video.video_status = map_video_status(details.get("status"))
    length = details.get("length")
    if length is not None:
        try:
            video.video_duration = float(length)
        except (TypeError, ValueError):
            pass
    if not keep_thumbnail:
        thumbnail = details.get("thumbnail") or details.get("poster")
        if thumbnail:
            video.thumbnail_url = thumbnail


def _changed_fields(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


def sync_from_vdocipher(video: PromoVideo, required: bool = False, overwrite_thumbnail: bool = False):
    """Refresh processing status with the promo key.

    Returns (error_message, http_status) or (None, None).
    When the promo key is missing and required is false, the row is saved as given.
    """
    if not video.vdocipher_video_id:
        video.video_status = "pending"
        if required:
            return "Link a VdoCipher video before refreshing status", 400
        return None, None
    service = get_promo_vdocipher_service()
    if service is None:
        if required:
            return "VDOCIPHER_PROMO_API_SECRET is not configured", 503
        if not video.video_status:
            video.video_status = "pending"
        return None, None
    try:
        details = service.get_video_details(video.vdocipher_video_id)
    except Exception as exc:
        message = str(exc)
        logger.warning("Promo video lookup failed for %s: %s", video.vdocipher_video_id, message)
        if "not found" in message.lower():
            return "Video was not found in VdoCipher", 400
        return "Could not read the video from VdoCipher", 503
    keep_thumbnail = bool(video.thumbnail_url) and not overwrite_thumbnail
    _apply_vdocipher_details(video, details, keep_thumbnail=keep_thumbnail)
    return None, None


def _incoming_payload() -> dict:
    """JSON body, or multipart form fields when a cover file is uploaded."""
    if request.form or request.files:
        payload = {}
        for key, value in request.form.items():
            if value == "" and key not in {"title", "vdocipher_video_id"}:
                continue
            payload[key] = value
        return payload
    return request.get_json(silent=True) or {}


def _uploaded_cover():
    """Return (cover_url, error). Both are None when no file was sent."""
    cover = request.files.get("cover") if request.files else None
    if cover is None or not getattr(cover, "filename", ""):
        return None, None
    return save_promo_cover(cover)


def _validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid video data"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", []))
    return f"{loc}: {first.get('msg')}" if loc else first.get("msg", "Invalid video data")


@promo_videos_bp.route("/promo-videos", methods=["GET"])
@jwt_required()
def list_promo_videos():
    db = None
    try:
        db = get_db()
        videos = (
            _active_query(db)
            .order_by(PromoVideo.sort_order.asc(), PromoVideo.id.asc())
            .all()
        )
        return jsonify({"status": "success", "data": [serialize_admin(video) for video in videos]})
    except Exception as exc:
        logger.exception("Failed to list promo videos")
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos/<int:video_id>", methods=["GET"])
@jwt_required()
def get_promo_video(video_id):
    db = None
    try:
        db = get_db()
        video = _active_query(db).filter(PromoVideo.id == video_id).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404
        return jsonify({"status": "success", "data": serialize_admin(video)})
    except Exception as exc:
        logger.exception("Failed to load promo video %s", video_id)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos", methods=["POST"])
@jwt_required()
def create_promo_video():
    db = None
    try:
        db = get_db()
        payload = _incoming_payload()
        data = PromoVideoCreate(**payload)
        title = data.title.strip()
        vdocipher_video_id = (data.vdocipher_video_id or "").strip() or None
        if not title:
            return jsonify({"status": "error", "message": "Title is required"}), 400
        if data.status not in PUBLICATION_STATUSES:
            return jsonify({"status": "error", "message": "status must be draft or published"}), 400
        if vdocipher_video_id and data.video_status and data.video_status not in VIDEO_STATUSES:
            return jsonify({
                "status": "error",
                "message": "video_status must be pending, processing, ready, or failed",
            }), 400

        user_id = int(get_jwt_identity())
        base_slug = slugify(data.slug or title)
        if not base_slug:
            return jsonify({"status": "error", "message": "slug could not be generated from the title"}), 400

        video = PromoVideo(
            title=title,
            slug=unique_slug(db, base_slug),
            description=(data.description or "").strip() or None,
            status=data.status,
            video_status="pending" if not vdocipher_video_id else (data.video_status or "pending"),
            vdocipher_video_id=vdocipher_video_id,
            thumbnail_url=(data.thumbnail_url or "").strip() or None,
            sort_order=data.sort_order,
            created_by=user_id,
            updated_by=user_id,
        )
        if vdocipher_video_id:
            error, code = sync_from_vdocipher(video, required=False)
            if error:
                return jsonify({"status": "error", "message": error}), code

        cover_url, cover_error = _uploaded_cover()
        if cover_error:
            return jsonify({"status": "error", "message": cover_error}), 400
        video.cover_url = cover_url

        db.add(video)
        db.commit()
        db.refresh(video)
        return jsonify({"status": "success", "data": serialize_admin(video)}), 201
    except ValidationError as exc:
        return jsonify({"status": "error", "message": _validation_message(exc)}), 400
    except Exception as exc:
        if db is not None:
            db.rollback()
        logger.exception("Failed to create promo video")
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos/<int:video_id>", methods=["PUT"])
@jwt_required()
def update_promo_video(video_id):
    db = None
    try:
        db = get_db()
        video = _active_query(db).filter(PromoVideo.id == video_id).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404

        payload = _incoming_payload()
        data = PromoVideoUpdate(**payload)
        fields = _changed_fields(data)

        if "title" in fields:
            title = (fields["title"] or "").strip()
            if not title:
                return jsonify({"status": "error", "message": "Title is required"}), 400
            video.title = title
        if "description" in fields:
            video.description = (fields["description"] or "").strip() or None
        if "status" in fields:
            if fields["status"] not in PUBLICATION_STATUSES:
                return jsonify({"status": "error", "message": "status must be draft or published"}), 400
            video.status = fields["status"]
        if "video_status" in fields and fields["video_status"] is not None:
            if fields["video_status"] not in VIDEO_STATUSES:
                return jsonify({
                    "status": "error",
                    "message": "video_status must be pending, processing, ready, or failed",
                }), 400
            if video.vdocipher_video_id:
                video.video_status = fields["video_status"]
        if "thumbnail_url" in fields:
            video.thumbnail_url = (fields["thumbnail_url"] or "").strip() or None
        if "sort_order" in fields and fields["sort_order"] is not None:
            video.sort_order = fields["sort_order"]
        if "slug" in fields and fields["slug"] is not None:
            base_slug = slugify(fields["slug"])
            if not base_slug:
                return jsonify({"status": "error", "message": "slug is invalid"}), 400
            video.slug = unique_slug(db, base_slug, exclude_id=video.id)
        if "vdocipher_video_id" in fields:
            vdocipher_video_id = (fields["vdocipher_video_id"] or "").strip() or None
            video.vdocipher_video_id = vdocipher_video_id
            if not vdocipher_video_id:
                video.video_status = "pending"
            else:
                error, code = sync_from_vdocipher(video, required=False)
                if error:
                    db.rollback()
                    return jsonify({"status": "error", "message": error}), code
        if not video.vdocipher_video_id:
            video.video_status = "pending"

        cover_url, cover_error = _uploaded_cover()
        if cover_error:
            return jsonify({"status": "error", "message": cover_error}), 400
        if cover_url:
            video.cover_url = cover_url

        video.updated_by = int(get_jwt_identity())
        db.commit()
        db.refresh(video)
        return jsonify({"status": "success", "data": serialize_admin(video)})
    except ValidationError as exc:
        return jsonify({"status": "error", "message": _validation_message(exc)}), 400
    except Exception as exc:
        if db is not None:
            db.rollback()
        logger.exception("Failed to update promo video %s", video_id)
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos/<int:video_id>", methods=["DELETE"])
@jwt_required()
def delete_promo_video(video_id):
    db = None
    try:
        db = get_db()
        video = _active_query(db).filter(PromoVideo.id == video_id).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404
        video.deleted_at = datetime.utcnow()
        video.updated_by = int(get_jwt_identity())
        # Free the public slug so a replacement video can reuse it.
        video.slug = f"{video.slug[:180]}-deleted-{video.id}"
        db.commit()
        return jsonify({"status": "success", "message": "Video deleted"})
    except Exception as exc:
        if db is not None:
            db.rollback()
        logger.exception("Failed to delete promo video %s", video_id)
        return jsonify({"status": "error", "message": str(exc)}), 400
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos/<int:video_id>/refresh-status", methods=["POST"])
@jwt_required()
def refresh_promo_video_status(video_id):
    db = None
    try:
        db = get_db()
        video = _active_query(db).filter(PromoVideo.id == video_id).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404
        error, code = sync_from_vdocipher(video, required=True, overwrite_thumbnail=True)
        if error:
            return jsonify({"status": "error", "message": error}), code
        video.updated_by = int(get_jwt_identity())
        db.commit()
        db.refresh(video)
        return jsonify({"status": "success", "data": serialize_admin(video)})
    except Exception as exc:
        if db is not None:
            db.rollback()
        logger.exception("Failed to refresh promo video %s", video_id)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos/public", methods=["GET"])
def list_public_promo_videos():
    """Published videos for the website. The VdoCipher id is not included."""
    db = None
    try:
        db = get_db()
        videos = (
            _active_query(db)
            .filter(PromoVideo.status == "published")
            .order_by(PromoVideo.sort_order.asc(), PromoVideo.id.asc())
            .all()
        )
        return jsonify({"status": "success", "data": [serialize_public(video) for video in videos]})
    except Exception as exc:
        logger.exception("Failed to list public promo videos")
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        if db is not None:
            db.close()


@promo_videos_bp.route("/promo-videos/public/<slug>/play", methods=["POST"])
def play_public_promo_video(slug):
    """Mint a short-lived playback OTP. No login. Drafts are not found."""
    db = None
    try:
        db = get_db()
        video = _active_query(db).filter(
            PromoVideo.slug == slug,
            PromoVideo.status == "published",
        ).first()
        if not video:
            return jsonify({"status": "error", "message": "Video not found"}), 404
        if not video.vdocipher_video_id or video.video_status != "ready":
            return jsonify({
                "status": "error",
                "message": "Video is not ready for playback.",
                "video_status": video.video_status or "pending",
            }), 425

        service = get_promo_vdocipher_service()
        if service is None:
            return jsonify({
                "status": "error",
                "message": "VDOCIPHER_PROMO_API_SECRET is not configured",
            }), 503
        try:
            otp_data = service.generate_playback_otp(video.vdocipher_video_id)
        except Exception as exc:
            logger.error("Failed to mint promo OTP for %s: %s", slug, exc)
            return jsonify({
                "status": "error",
                "message": "Failed to generate video credentials",
            }), 503
        if not otp_data.get("otp") or not otp_data.get("playbackInfo"):
            return jsonify({
                "status": "error",
                "message": "Failed to generate video credentials",
            }), 503

        return jsonify({
            "status": "success",
            "data": {
                "otp": otp_data.get("otp"),
                "playbackInfo": otp_data.get("playbackInfo"),
                "video": serialize_public(video),
            },
        })
    except Exception as exc:
        logger.exception("Failed to play promo video %s", slug)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        if db is not None:
            db.close()
