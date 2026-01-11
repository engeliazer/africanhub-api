from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, ForeignKey, Float
from sqlalchemy.sql import func
from database.db_connector import Base
from datetime import datetime

class StudyMaterialCategory(Base):
    __tablename__ = 'study_material_categories'

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_protected = Column(Integer, default=0)
    created_by = Column(BigInteger, nullable=False)
    updated_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

class SubtopicMaterial(Base):
    __tablename__ = "subtopic_materials"
    
    id = Column(BigInteger, primary_key=True, index=True)
    subtopic_id = Column(BigInteger, ForeignKey('sub_topics.id', ondelete='CASCADE'), nullable=False)
    material_category_id = Column(BigInteger, ForeignKey('study_material_categories.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    material_path = Column(Text, nullable=False)
    # Optional alternative storage path for B2
    b2_material_path = Column(Text, nullable=True)
    extension_type = Column(String(50), nullable=False)
    video_duration = Column(Float, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    processing_status = Column(String(20), default='pending')  # pending, processing, completed, failed
    processing_progress = Column(Integer, default=0)  # 0-100
    processing_error = Column(Text, nullable=True)  # Error message if processing fails
    # Storage location selector: 'local' or 'b2'. Default to 'local' for backwards compatibility
    storage_location = Column(String(10), default='local')
    # VdoCipher integration fields
    vdocipher_video_id = Column(String(255), nullable=True, index=True)
    video_status = Column(String(50), nullable=True, default='pending', index=True)  # pending, processing, ready, failed
    video_thumbnail_url = Column(Text, nullable=True)
    video_poster_url = Column(Text, nullable=True)
    requires_drm = Column(Boolean, default=False)  # TRUE = Use VdoCipher, FALSE = Use HLS
    created_by = Column(BigInteger, nullable=False)
    updated_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now()) 