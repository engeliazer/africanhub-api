import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from database.db_connector import Base


class WatchStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


VIDEO_EXTENSIONS = ("mp4", "webm", "avi", "mov", "wmv", "mkv")


class VideoWatchSession(Base):
    __tablename__ = "video_watch_sessions"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    session_token = Column(String(36), nullable=False, unique=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(
        BigInteger,
        ForeignKey("subtopic_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    watched_seconds = Column(Float, nullable=False, default=0)
    max_position_seconds = Column(Float, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    ip_address = Column(String(45), nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    last_heartbeat_at = Column(DateTime, nullable=False, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)


class VideoWatchProgress(Base):
    __tablename__ = "video_watch_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "material_id", name="uq_video_watch_progress_user_material"),
    )

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(
        BigInteger,
        ForeignKey("subtopic_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_watched_seconds = Column(Float, nullable=False, default=0)
    max_position_seconds = Column(Float, nullable=False, default=0)
    session_count = Column(Integer, nullable=False, default=0)
    completion_percentage = Column(Float, nullable=False, default=0)
    status = Column(String(20), nullable=False, default=WatchStatus.not_started.value)
    first_watched_at = Column(DateTime, nullable=True)
    last_watched_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
