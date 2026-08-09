import logging
import uuid
from datetime import datetime
from typing import Optional

from flask import request
from sqlalchemy.orm import Session

from studies.models.models import SubtopicMaterial
from subjects.models.models import SubTopic, Topic
from video_tracking.models.models import (
    VIDEO_EXTENSIONS,
    VideoWatchProgress,
    VideoWatchSession,
    WatchStatus,
)

logger = logging.getLogger(__name__)

COMPLETION_THRESHOLD = 90.0
MAX_HEARTBEAT_DELTA = 35.0
WALL_CLOCK_TOLERANCE = 5.0
STALE_SESSION_SECONDS = 120


def default_watch_progress() -> dict:
    return {
        "total_watched_seconds": 0,
        "max_position_seconds": 0,
        "completion_percentage": 0,
        "status": WatchStatus.not_started.value,
        "session_count": 0,
        "first_watched_at": None,
        "last_watched_at": None,
        "completed_at": None,
    }


def is_video_material(extension_type: str) -> bool:
    return extension_type.lower() in VIDEO_EXTENSIONS


def derive_subject_summary(material_entries: list[dict]) -> dict:
    """
    Derive subject-level progress from video material rows on demand.
    Each entry must include video_duration and watch progress fields.
    Completion is duration-weighted: sum(watched) / sum(duration).
    """
    if not material_entries:
        return {
            "video_count": 0,
            "videos_completed": 0,
            "videos_in_progress": 0,
            "videos_not_started": 0,
            "total_video_duration": 0,
            "total_watched_seconds": 0,
            "completion_percentage": 0,
            "status": WatchStatus.not_started.value,
            "first_watched_at": None,
            "last_watched_at": None,
            "completed_at": None,
        }

    total_video_duration = 0.0
    total_watched_seconds = 0.0
    videos_completed = 0
    videos_in_progress = 0
    videos_not_started = 0
    first_watched_at = None
    last_watched_at = None
    completed_at_values = []

    for entry in material_entries:
        duration = float(entry.get("video_duration") or 0)
        watched = float(entry.get("total_watched_seconds") or 0)
        status = entry.get("status", WatchStatus.not_started.value)

        if duration > 0:
            total_video_duration += duration
        total_watched_seconds += watched

        if status == WatchStatus.completed.value:
            videos_completed += 1
        elif status == WatchStatus.in_progress.value:
            videos_in_progress += 1
        else:
            videos_not_started += 1

        if entry.get("first_watched_at"):
            if first_watched_at is None or entry["first_watched_at"] < first_watched_at:
                first_watched_at = entry["first_watched_at"]

        if entry.get("last_watched_at"):
            if last_watched_at is None or entry["last_watched_at"] > last_watched_at:
                last_watched_at = entry["last_watched_at"]

        if entry.get("completed_at"):
            completed_at_values.append(entry["completed_at"])

    video_count = len(material_entries)
    if total_video_duration > 0:
        completion_percentage = round(
            min((total_watched_seconds / total_video_duration) * 100, 100.0),
            2,
        )
    else:
        completion_percentage = 0.0

    if video_count > 0 and videos_completed == video_count:
        subject_status = WatchStatus.completed.value
        completed_at = max(completed_at_values) if completed_at_values else None
    elif total_watched_seconds > 0 or videos_in_progress > 0 or videos_completed > 0:
        subject_status = WatchStatus.in_progress.value
        completed_at = None
    else:
        subject_status = WatchStatus.not_started.value
        completed_at = None

    return {
        "video_count": video_count,
        "videos_completed": videos_completed,
        "videos_in_progress": videos_in_progress,
        "videos_not_started": videos_not_started,
        "total_video_duration": total_video_duration,
        "total_watched_seconds": total_watched_seconds,
        "completion_percentage": completion_percentage,
        "status": subject_status,
        "first_watched_at": first_watched_at,
        "last_watched_at": last_watched_at,
        "completed_at": completed_at,
    }


def collect_video_entries_from_subject_tree(subject: dict) -> list[dict]:
    """Collect video material progress rows from a nested approved-courses subject."""
    entries = []
    for topic in subject.get("topics", []):
        for subtopic in topic.get("subtopics", []):
            for category in subtopic.get("materials", []):
                for file_entry in category.get("files", []):
                    watch_progress = file_entry.get("watch_progress")
                    if watch_progress is None:
                        continue
                    entries.append(
                        {
                            "video_duration": file_entry.get("video_duration") or 0,
                            **watch_progress,
                        }
                    )
    return entries


class TrackingController:
    def __init__(self, db: Session):
        self.db = db

    def start_session(self, user_id: int, material_id: int) -> dict:
        material = self.db.query(SubtopicMaterial).filter_by(id=material_id).first()
        if not material:
            return {"error": "Material not found", "status_code": 404}

        if material.extension_type.lower() not in VIDEO_EXTENSIONS:
            return {
                "error": "Material is not a trackable video",
                "status_code": 400,
            }

        duration = material.video_duration or 0
        if duration <= 0:
            return {
                "error": "Material has no video duration — cannot track",
                "status_code": 400,
            }

        self._close_stale_sessions(user_id)
        now = datetime.utcnow()

        session = VideoWatchSession(
            session_token=str(uuid.uuid4()),
            user_id=user_id,
            material_id=material_id,
            ip_address=request.remote_addr,
            started_at=now,
            last_heartbeat_at=now,
        )
        self.db.add(session)

        progress = self._get_or_create_progress(user_id, material_id)
        progress.session_count += 1
        if progress.first_watched_at is None:
            progress.first_watched_at = now
        progress.last_watched_at = now
        if progress.status != WatchStatus.completed.value:
            progress.status = WatchStatus.in_progress.value

        self.db.commit()

        return {
            "session_token": session.session_token,
            "material_id": material_id,
            "video_duration": duration,
        }

    def heartbeat(
        self,
        user_id: int,
        session_token: str,
        current_position: float,
        watched_delta: float,
    ) -> dict:
        return self._update_session(
            user_id=user_id,
            session_token=session_token,
            current_position=current_position,
            watched_delta=watched_delta,
            end_session=False,
        )

    def end_session(
        self,
        user_id: int,
        session_token: str,
        current_position: float,
        watched_delta: float,
    ) -> dict:
        return self._update_session(
            user_id=user_id,
            session_token=session_token,
            current_position=current_position,
            watched_delta=watched_delta,
            end_session=True,
        )

    def get_progress_map(self, user_id: int, material_ids: list[int]) -> dict[int, dict]:
        if not material_ids:
            return {}

        progress_rows = (
            self.db.query(VideoWatchProgress)
            .filter(
                VideoWatchProgress.user_id == user_id,
                VideoWatchProgress.material_id.in_(material_ids),
            )
            .all()
        )

        return {
            row.material_id: self._progress_fields(row)
            for row in progress_rows
        }

    def get_material_progress(self, user_id: int, material_id: int) -> dict:
        material = self.db.query(SubtopicMaterial).filter_by(id=material_id).first()
        if not material:
            return {"error": "Material not found", "status_code": 404}

        progress = (
            self.db.query(VideoWatchProgress)
            .filter_by(user_id=user_id, material_id=material_id)
            .first()
        )

        return self._serialize_progress(material, progress)

    def get_subject_progress(self, user_id: int, subject_id: int) -> dict:
        materials = (
            self.db.query(SubtopicMaterial)
            .join(SubTopic, SubtopicMaterial.subtopic_id == SubTopic.id)
            .join(Topic, SubTopic.topic_id == Topic.id)
            .filter(
                Topic.subject_id == subject_id,
                SubtopicMaterial.extension_type.in_(VIDEO_EXTENSIONS),
            )
            .order_by(SubtopicMaterial.name)
            .all()
        )

        if not materials:
            return {
                "subject_id": subject_id,
                "summary": derive_subject_summary([]),
                "materials": [],
            }

        material_ids = [material.id for material in materials]
        progress_rows = (
            self.db.query(VideoWatchProgress)
            .filter(
                VideoWatchProgress.user_id == user_id,
                VideoWatchProgress.material_id.in_(material_ids),
            )
            .all()
        )
        progress_by_material = {row.material_id: row for row in progress_rows}

        summary_entries = [
            {
                "video_duration": material.video_duration or 0,
                **self._progress_fields(progress_by_material.get(material.id)),
            }
            for material in materials
        ]

        return {
            "subject_id": subject_id,
            "summary": derive_subject_summary(summary_entries),
            "materials": [
                self._serialize_progress(material, progress_by_material.get(material.id))
                for material in materials
            ],
        }

    def _update_session(
        self,
        user_id: int,
        session_token: str,
        current_position: float,
        watched_delta: float,
        end_session: bool,
    ) -> dict:
        session = (
            self.db.query(VideoWatchSession)
            .filter_by(session_token=session_token, user_id=user_id)
            .first()
        )
        if not session:
            return {"error": "Session not found", "status_code": 404}

        if not session.is_active:
            return {"error": "Session is no longer active", "status_code": 400}

        material = self._get_trackable_material(session.material_id)
        if not material:
            return {"error": "Material not found", "status_code": 404}

        validated_delta = self._validate_watched_delta(session, watched_delta)
        now = datetime.utcnow()

        session.watched_seconds += validated_delta
        session.max_position_seconds = max(session.max_position_seconds, current_position)
        session.last_heartbeat_at = now

        progress = self._get_or_create_progress(user_id, session.material_id)
        progress.total_watched_seconds += validated_delta
        progress.max_position_seconds = max(progress.max_position_seconds, current_position)
        progress.last_watched_at = now
        self._recalculate_completion(progress, material)

        if end_session:
            session.is_active = False
            session.ended_at = now

        self.db.commit()

        return {
            "session_token": session.session_token,
            "watched_delta_applied": validated_delta,
            "completion_percentage": progress.completion_percentage,
            "status": progress.status,
            "total_watched_seconds": progress.total_watched_seconds,
        }

    def _validate_watched_delta(self, session: VideoWatchSession, watched_delta: float) -> float:
        delta = max(float(watched_delta or 0), 0.0)
        delta = min(delta, MAX_HEARTBEAT_DELTA)

        if session.last_heartbeat_at:
            elapsed = (datetime.utcnow() - session.last_heartbeat_at).total_seconds()
            max_allowed = elapsed + WALL_CLOCK_TOLERANCE
            delta = min(delta, max_allowed)

        return delta

    def _recalculate_completion(
        self,
        progress: VideoWatchProgress,
        material: SubtopicMaterial,
    ) -> None:
        duration = material.video_duration or 0
        if duration <= 0:
            return

        percentage = min((progress.total_watched_seconds / duration) * 100, 100.0)
        progress.completion_percentage = round(percentage, 2)

        if progress.status == WatchStatus.completed.value:
            return

        if percentage >= COMPLETION_THRESHOLD:
            progress.status = WatchStatus.completed.value
            if progress.completed_at is None:
                progress.completed_at = datetime.utcnow()
        elif progress.session_count > 0 or progress.total_watched_seconds > 0:
            progress.status = WatchStatus.in_progress.value

    def _close_stale_sessions(self, user_id: int) -> None:
        cutoff = datetime.utcnow().timestamp() - STALE_SESSION_SECONDS
        stale_sessions = (
            self.db.query(VideoWatchSession)
            .filter(
                VideoWatchSession.user_id == user_id,
                VideoWatchSession.is_active.is_(True),
            )
            .all()
        )

        for session in stale_sessions:
            if session.last_heartbeat_at.timestamp() < cutoff:
                session.is_active = False
                session.ended_at = datetime.utcnow()

    def _get_trackable_material(self, material_id: int) -> Optional[SubtopicMaterial]:
        material = self.db.query(SubtopicMaterial).filter_by(id=material_id).first()
        if not material:
            return None
        if material.extension_type.lower() not in VIDEO_EXTENSIONS:
            return None
        return material

    def _get_or_create_progress(self, user_id: int, material_id: int) -> VideoWatchProgress:
        progress = (
            self.db.query(VideoWatchProgress)
            .filter_by(user_id=user_id, material_id=material_id)
            .first()
        )
        if progress:
            return progress

        progress = VideoWatchProgress(
            user_id=user_id,
            material_id=material_id,
            status=WatchStatus.not_started.value,
        )
        self.db.add(progress)
        self.db.flush()
        return progress

    def _serialize_progress(
        self,
        material: SubtopicMaterial,
        progress: Optional[VideoWatchProgress],
    ) -> dict:
        payload = self._progress_fields(progress)
        payload.update(
            {
                "material_id": material.id,
                "material_name": material.name,
                "subtopic_id": material.subtopic_id,
                "video_duration": material.video_duration,
            }
        )
        return payload

    def _progress_fields(self, progress: Optional[VideoWatchProgress]) -> dict:
        if not progress:
            return default_watch_progress()

        return {
            "total_watched_seconds": progress.total_watched_seconds,
            "max_position_seconds": progress.max_position_seconds,
            "completion_percentage": progress.completion_percentage,
            "status": progress.status,
            "session_count": progress.session_count,
            "first_watched_at": (
                progress.first_watched_at.isoformat() if progress.first_watched_at else None
            ),
            "last_watched_at": (
                progress.last_watched_at.isoformat() if progress.last_watched_at else None
            ),
            "completed_at": (
                progress.completed_at.isoformat() if progress.completed_at else None
            ),
        }
