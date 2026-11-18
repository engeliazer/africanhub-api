"""Upload, list, and attendance-gated download helpers for event zip resources."""

from __future__ import annotations

import os
import re
import uuid
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from sqlalchemy.orm import Session, joinedload

from certificates.models.models import CertificateParticipant, CertificateTrainingContext
from certificates.services.participant_service import resolve_certificate_participant_identity
from config import UPLOAD_FOLDER
from events.models.models import Event, EventResource

RESOURCE_EXTENSIONS = {"zip"}
RESOURCES_SUBDIR = "event_resources"


def attendance_number_from_request(args) -> str:
    """Accept attendance_number (preferred) or serial_no (certificate alias)."""
    return (
        (args.get("attendance_number") or args.get("serial_no") or "")
        .strip()
    )


def unsafe_zip_member(name: str) -> bool:
    normalized = (name or "").replace("\\", "/")
    if normalized.startswith("/"):
        return True
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    return any(part == ".." for part in parts)


def zip_archive_error(path: str) -> Optional[str]:
    if not zipfile.is_zipfile(path):
        return "File is not a valid zip archive"
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not any(not info.is_dir() for info in infos):
                return "Zip archive is empty"
            for info in infos:
                if unsafe_zip_member(info.filename):
                    return "Zip archive contains unsafe paths"
            bad_member = archive.testzip()
            if bad_member is not None:
                return "Zip archive is corrupted"
    except zipfile.BadZipFile:
        return "File is not a valid zip archive"
    return None


def resource_download_name(resource: EventResource) -> str:
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", resource.name or "resource").strip(" ._")
    if not base:
        base = f"event-resource-{resource.id}"
    if not base.lower().endswith(".zip"):
        base = f"{base}.zip"
    return base


def absolute_resource_path(resource: EventResource) -> str:
    stored = resource.file_path or ""
    if os.path.isabs(stored) or stored.startswith("storage/"):
        return stored
    return os.path.join(UPLOAD_FOLDER, stored)


def list_active_resources(db: Session, event_id: int) -> List[EventResource]:
    return (
        db.query(EventResource)
        .filter(
            EventResource.event_id == event_id,
            EventResource.deleted_at.is_(None),
        )
        .order_by(EventResource.id.asc())
        .all()
    )


def count_active_resources(db: Session, event_id: int) -> int:
    return (
        db.query(EventResource)
        .filter(
            EventResource.event_id == event_id,
            EventResource.deleted_at.is_(None),
        )
        .count()
    )


def get_active_resource(
    db: Session,
    event_id: int,
    resource_id: int,
) -> Optional[EventResource]:
    return (
        db.query(EventResource)
        .filter(
            EventResource.id == resource_id,
            EventResource.event_id == event_id,
            EventResource.deleted_at.is_(None),
        )
        .first()
    )


def resource_to_dict(
    resource: EventResource,
    *,
    attendance_number: Optional[str] = None,
    include_admin_fields: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": resource.id,
        "event_id": resource.event_id,
        "name": resource.name,
        "description": resource.description,
        "extension_type": resource.extension_type,
        "file_type": "resource",
        "file_size": resource.file_size,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }
    if include_admin_fields:
        payload.update({
            "file_path": resource.file_path,
            "original_filename": resource.original_filename,
            "created_by": resource.created_by,
            "updated_by": resource.updated_by,
            "download_url": f"/api/events/{resource.event_id}/resources/{resource.id}/download",
        })
    elif attendance_number:
        encoded = quote(attendance_number, safe="")
        payload["download_url"] = (
            f"/api/events/public/resources/{resource.id}/download"
            f"?attendance_number={encoded}"
        )
    return payload


def save_event_resource_file(
    event_id: int,
    name: str,
    file_storage,
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
    """
    Persist a zip under uploads/event_resources/<event_id>/<uuid>/.

    Returns (relative_path, original_filename, file_size, error).
    """
    original_filename = (file_storage.filename or "").strip()
    if not original_filename:
        return None, None, None, "No selected file"

    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in RESOURCE_EXTENSIONS:
        return None, None, None, "Only .zip files are allowed for event resources"

    now = datetime.now()
    resource_uuid = str(uuid.uuid4())
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", name).strip("_") or "resource"
    filename = f"{safe_name}_{now.strftime('%Y%m%d_%H%M%S')}.zip"
    relative_dir = os.path.join(RESOURCES_SUBDIR, str(event_id), resource_uuid)
    absolute_dir = os.path.join(UPLOAD_FOLDER, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)

    absolute_path = os.path.join(absolute_dir, filename)
    file_storage.save(absolute_path)

    archive_error = zip_archive_error(absolute_path)
    if archive_error:
        try:
            os.remove(absolute_path)
        except OSError:
            pass
        return None, None, None, archive_error

    relative_path = os.path.join(relative_dir, filename).replace("\\", "/")
    return relative_path, original_filename, os.path.getsize(absolute_path), None


def create_event_resource(
    db: Session,
    event: Event,
    *,
    name: str,
    description: Optional[str],
    file_storage,
    user_id: int,
) -> Tuple[Optional[EventResource], Optional[str]]:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return None, "name is required"

    relative_path, original_filename, file_size, error = save_event_resource_file(
        event.id,
        cleaned_name,
        file_storage,
    )
    if error:
        return None, error

    resource = EventResource(
        event_id=event.id,
        name=cleaned_name,
        description=(description or "").strip() or None,
        file_path=relative_path,
        original_filename=original_filename,
        extension_type="zip",
        file_size=file_size,
        created_by=user_id,
        updated_by=user_id,
    )
    try:
        db.add(resource)
        db.commit()
        db.refresh(resource)
    except Exception:
        db.rollback()
        absolute_path = os.path.join(UPLOAD_FOLDER, relative_path)
        if os.path.isfile(absolute_path):
            try:
                os.remove(absolute_path)
            except OSError:
                pass
        raise
    return resource, None


def soft_delete_event_resource(
    db: Session,
    resource: EventResource,
    user_id: int,
) -> None:
    resource.deleted_at = datetime.utcnow()
    resource.updated_by = user_id
    db.commit()


def resolve_event_by_attendance_number(
    db: Session,
    attendance_number: str,
) -> Tuple[
    Optional[Event],
    Optional[CertificateParticipant],
    Optional[CertificateTrainingContext],
    Optional[str],
    Optional[str],
]:
    """
    Map a certificate attendance number (serial_no) to its event.

    Returns (event, participant, context, participant_name, error).
    """
    normalized = (attendance_number or "").strip()
    if not normalized:
        return None, None, None, None, "attendance_number is required"

    participant = (
        db.query(CertificateParticipant)
        .options(joinedload(CertificateParticipant.training_context))
        .filter(
            CertificateParticipant.serial_no == normalized,
            CertificateParticipant.deleted_at.is_(None),
        )
        .first()
    )
    if not participant:
        return None, None, None, None, "Attendance number not found"

    context = participant.training_context
    if context is None or context.deleted_at is not None:
        return None, participant, None, None, "Training context not found"

    if (context.training_type or "").strip().lower() != "event":
        return None, participant, context, None, "Attendance number is not linked to an event"

    event = db.query(Event).filter(Event.id == context.training_id).first()
    if not event:
        return None, participant, context, None, "Event not found"

    identity, identity_error = resolve_certificate_participant_identity(db, participant, context)
    if identity_error:
        return None, participant, context, None, identity_error

    return event, participant, context, identity.display_name, None
