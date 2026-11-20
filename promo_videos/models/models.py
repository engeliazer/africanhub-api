from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from database.base import Base


class PromoVideo(Base):
    """Website promotional video. Playback uses the restricted VdoCipher key."""

    __tablename__ = "promo_videos"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    # draft: hidden from the website. published: listed publicly.
    status = Column(String(20), nullable=False, default="draft", index=True)
    # VdoCipher processing state, independent of whether we publish the video.
    video_status = Column(String(50), nullable=False, default="pending", index=True)
    # Empty until an admin links the VdoCipher video. Playback stays pending until then.
    vdocipher_video_id = Column(String(255), nullable=True, index=True)
    thumbnail_url = Column(Text, nullable=True)
    # Optional image uploaded by an admin. Shown before playback on the website.
    cover_url = Column(Text, nullable=True)
    video_duration = Column(Float, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    deleted_at = Column(DateTime, nullable=True)
