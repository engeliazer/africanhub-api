from flask import Blueprint, jsonify, request, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from studies.models.models import SubtopicMaterial, StudyMaterialCategory
from studies.models.schemas import SubtopicMaterialCreate, SubtopicMaterialUpdate, SubtopicMaterialInDB
from subjects.models.models import SubTopic
from database.db_connector import db_session
from auth.services.device_fingerprint_service import DeviceFingerprintService
from datetime import datetime, timedelta
import os
import re
import glob
import json
import struct
import wave
import uuid
import subprocess
import shutil
import tempfile
import requests
import logging
from config import UPLOAD_FOLDER, allowed_file, ALLOWED_EXTENSIONS
from werkzeug.utils import secure_filename
import ffmpeg
# OLD TASKS - No longer used, replaced by tasks_streamlined
# from tasks import process_video  # Import from tasks.py
# from tasks_b2 import process_video_b2  # B2 processing disabled
# from tasks_local import process_video_local  # Import local video processing task

# Configure logging
logger = logging.getLogger(__name__)

subtopic_materials_bp = Blueprint('subtopic_materials', __name__)

# Create HLS directory
HLS_FOLDER = os.path.join(UPLOAD_FOLDER, 'hls')
os.makedirs(HLS_FOLDER, exist_ok=True)

def is_hls_ready(manifest_path: str) -> bool:
    """Return True if manifest exists and at least one .ts segment exists next to it."""
    try:
        # Resolve to absolute path
        abs_manifest = manifest_path
        if not os.path.isabs(abs_manifest):
            if abs_manifest.startswith('storage/'):
                abs_manifest = os.path.join(os.getcwd(), abs_manifest)
            else:
                abs_manifest = os.path.join(UPLOAD_FOLDER, abs_manifest)

        if not os.path.exists(abs_manifest):
            return False

        hls_dir = os.path.dirname(abs_manifest)
        # Must have at least one .ts file
        ts_candidates = glob.glob(os.path.join(hls_dir, '*.ts'))
        if not ts_candidates:
            return False

        # Basic manifest sanity: non-empty and references at least one .ts line
        try:
            with open(abs_manifest, 'r') as f:
                content = f.read()
                if '#EXTM3U' not in content:
                    return False
                if '.ts' not in content:
                    return False
        except Exception:
            return False

        return True
    except Exception:
        return False

def is_file_older_than_days(file_path: str, days: int = 1) -> bool:
    """Return True if file exists and its modification time is older than N days."""
    try:
        if not os.path.exists(file_path):
            return False
        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        return datetime.now() - file_mtime >= timedelta(days=days)
    except Exception:
        # On any error, be conservative and do not treat as old
        return False

def repair_incomplete_manifest(manifest_path: str) -> str:
    """Repair an incomplete HLS manifest by scanning for all segments and regenerating the manifest."""
    try:
        manifest_dir = os.path.dirname(manifest_path)
        if not os.path.exists(manifest_dir):
            return manifest_path
            
        # Find all segment files
        segment_files = []
        for file in os.listdir(manifest_dir):
            if file.endswith('.ts') and file.startswith('segment_'):
                segment_files.append(file)
        
        if not segment_files:
            return manifest_path
            
        # Sort segments naturally
        def natural_sort_key(filename):
            import re
            match = re.search(r'segment_(\d+)\.ts', filename)
            return int(match.group(1)) if match else 0
            
        segment_files.sort(key=natural_sort_key)
        
        # Read existing manifest to get headers and duration info
        with open(manifest_path, 'r') as f:
            existing_content = f.read()
        
        # Extract headers (everything before first segment)
        lines = existing_content.split('\n')
        headers = []
        segment_entries = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip() and not line.startswith('#') and '.' in line:
                # This is a segment line, start collecting segment entries
                break
            headers.append(line)
            i += 1
        
        # Collect existing segment entries with durations
        while i < len(lines):
            if lines[i].startswith('#EXTINF'):
                duration_line = lines[i]
                i += 1
                if i < len(lines) and not lines[i].startswith('#'):
                    segment_line = lines[i]
                    segment_entries.append((duration_line, segment_line))
                i += 1
            else:
                i += 1
        
        # Create new manifest with all segments
        new_content = '\n'.join(headers) + '\n'
        
        # Add VOD type if missing
        if '#EXT-X-PLAYLIST-TYPE:VOD' not in new_content:
            new_content = new_content.replace('#EXTM3U', '#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD')
        
        # Add all segments with their durations
        for segment_file in segment_files:
            # Try to find duration from existing entries
            duration = 8.333333  # Default duration
            for dur_line, seg_line in segment_entries:
                if segment_file in seg_line:
                    duration = float(dur_line.split(',')[0].split(':')[1])
                    break
            
            new_content += f'#EXTINF:{duration},\n{segment_file}\n'
        
        # Add ENDLIST
        new_content += '#EXT-X-ENDLIST\n'
        
        # Write repaired manifest
        with open(manifest_path, 'w') as f:
            f.write(new_content)
            
        print(f"Repaired manifest: {manifest_path}")
        return manifest_path
        
    except Exception as e:
        print(f"Failed to repair manifest {manifest_path}: {e}")
        return manifest_path

def normalize_vod_manifest(lines: List[str]) -> List[str]:
    """Normalize an HLS manifest to behave like VOD:
    - Remove any EXT-X-START to avoid jumping near the live edge
    - Ensure EXT-X-PLAYLIST-TYPE:VOD is present
    - Ensure EXT-X-ENDLIST is present at the end
    - Sort segments in ascending order
    """
    output: List[str] = []
    has_vod_type = False
    has_endlist = False
    media_sequence_set = False
    segments_with_duration = []  # Store (duration, segment) pairs for sorting

    for line in lines:
        if line.startswith('#EXT-X-START'):
            # Skip start offset tags to default player to start from the beginning
            continue
        if line.startswith('#EXT-X-PLAYLIST-TYPE'):
            # Force VOD
            output.append('#EXT-X-PLAYLIST-TYPE:VOD')
            has_vod_type = True
            continue
        if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
            # Force media sequence to 0 for VOD to start at the first segment
            output.append('#EXT-X-MEDIA-SEQUENCE:0')
            media_sequence_set = True
            continue
        if line.startswith('#EXT-X-ENDLIST'):
            has_endlist = True
            # Do not append now; we'll ensure single ENDLIST at the end
            continue
        if line.startswith('#EXTINF'):
            # Store duration info for sorting
            duration = float(line.split(',')[0].split(':')[1])
            segments_with_duration.append((duration, line))
            continue
        if line.strip() and not line.startswith('#'):
            # This is a segment filename - pair it with the last duration
            if segments_with_duration:
                duration, duration_line = segments_with_duration[-1]
                segments_with_duration[-1] = (duration, duration_line, line)
            else:
                # Fallback if no duration found
                segments_with_duration.append((0.0, '', line))
            continue
        output.append(line)

    # Sort segments by filename (natural sort for segment_000.ts, segment_001.ts, etc.)
    def natural_sort_key(item):
        if len(item) == 3:
            duration, duration_line, segment = item
            # Extract numeric part from segment filename for sorting
            import re
            match = re.search(r'segment_(\d+)\.ts', segment)
            if match:
                return int(match.group(1))
        return 0

    segments_with_duration.sort(key=natural_sort_key)

    # Rebuild manifest with sorted segments
    for item in segments_with_duration:
        if len(item) == 3:
            duration, duration_line, segment = item
            output.append(duration_line)
            output.append(segment)

    # Insert VOD type and MEDIA-SEQUENCE after #EXTM3U if missing
    if not has_vod_type:
        try:
            idx = next(i for i, l in enumerate(output) if l.strip() == '#EXTM3U')
            output.insert(idx + 1, '#EXT-X-PLAYLIST-TYPE:VOD')
        except StopIteration:
            # If malformed and no EXTM3U, just prepend
            output.insert(0, '#EXTM3U')
            output.insert(1, '#EXT-X-PLAYLIST-TYPE:VOD')
    if not media_sequence_set:
        try:
            idx = next(i for i, l in enumerate(output) if l.strip() == '#EXTM3U')
            # Ensure MEDIA-SEQUENCE immediately after EXTM3U (or after PLAYLIST-TYPE if present)
            insert_idx = idx + 1
            if len(output) > insert_idx and output[insert_idx].startswith('#EXT-X-PLAYLIST-TYPE'):
                insert_idx += 1
            output.insert(insert_idx, '#EXT-X-MEDIA-SEQUENCE:0')
        except StopIteration:
            output.insert(0, '#EXTM3U')
            output.insert(1, '#EXT-X-PLAYLIST-TYPE:VOD')
            output.insert(2, '#EXT-X-MEDIA-SEQUENCE:0')
    
    # Add explicit start time to force beginning playback
    try:
        idx = next(i for i, l in enumerate(output) if l.strip() == '#EXTM3U')
        # Insert START-TIME after EXTM3U and other headers
        insert_idx = idx + 1
        while insert_idx < len(output) and output[insert_idx].startswith('#EXT-X-'):
            insert_idx += 1
        output.insert(insert_idx, '#EXT-X-START:TIME-OFFSET=0.0')
    except StopIteration:
        output.insert(0, '#EXTM3U')
        output.insert(1, '#EXT-X-PLAYLIST-TYPE:VOD')
        output.insert(2, '#EXT-X-MEDIA-SEQUENCE:0')
        output.insert(3, '#EXT-X-START:TIME-OFFSET=0.0')

    # Ensure ENDLIST
    if not has_endlist:
        output.append('#EXT-X-ENDLIST')

    return output

def get_mp4_duration(filename):
    """Get the duration of an MP4 video file."""
    try:
        with open(filename, 'rb') as f:
            # Skip to the 'moov' atom
            while True:
                size = struct.unpack('>I', f.read(4))[0]
                atom_type = f.read(4)
                if atom_type == b'moov':
                    break
                f.seek(size - 8, 1)
            
            # Find 'mvhd' atom
            while True:
                size = struct.unpack('>I', f.read(4))[0]
                atom_type = f.read(4)
                if atom_type == b'mvhd':
                    f.seek(12, 1)  # Skip version and flags
                    time_scale = struct.unpack('>I', f.read(4))[0]
                    duration = struct.unpack('>I', f.read(4))[0]
                    return float(duration) / time_scale
                f.seek(size - 8, 1)
    except Exception as e:
        print(f"Error reading MP4 duration: {str(e)}")
        return None

def convert_time_to_seconds(time_str):
    """Convert time string in HH:MM:SS format to seconds."""
    try:
        # Split the time string into hours, minutes, seconds
        h, m, s = map(int, time_str.split(':'))
        # Convert to total seconds
        return h * 3600 + m * 60 + s
    except Exception as e:
        print(f"Error converting time string to seconds: {str(e)}")
        return None

@subtopic_materials_bp.route('/study-materials/subtopic-materials', methods=['GET', 'POST'])
@jwt_required()
def get_materials():
    try:
        current_user_id = get_jwt_identity()
        
        # Get device fingerprint from request body or query params
        fingerprint_data = None
        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                fingerprint_data = data.get('device_fingerprint') if data else None
            else:
                fingerprint_data = request.form.get('device_fingerprint')
        
        if not fingerprint_data:
            return jsonify({
                "status": "error",
                "message": "Device fingerprint is required"
            }), 400
            
        # Initialize device fingerprint service
        device_service = DeviceFingerprintService(db_session)
        
        # Get or create device record
        device = device_service.get_or_create_device(current_user_id, fingerprint_data, current_user_id)
        
        # Check if device is allowed to access materials
        is_authorized = device_service.check_device_access(current_user_id, device.visitor_id)
        
        # Get pagination and filter parameters from query string
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        skip = (page - 1) * per_page
        subtopic_id = request.args.get('subtopic_id', type=int)
        material_category_id = request.args.get('material_category_id', type=int)

        # Build query
        query = db_session.query(SubtopicMaterial)
        
        if subtopic_id:
            query = query.filter(SubtopicMaterial.subtopic_id == subtopic_id)
        if material_category_id:
            query = query.filter(SubtopicMaterial.material_category_id == material_category_id)

        # Get total count
        total = query.count()
        
        # Get paginated materials
        materials = query.offset(skip).limit(per_page).all()

        # B2 migration disabled: no auto-migration of local materials

        # Serialize materials
        serialized_materials = []
        if is_authorized:
            for material in materials:
                serialized_materials.append({
                    "id": material.id,
                    "subtopic_id": material.subtopic_id,
                    "material_category_id": material.material_category_id,
                    "name": material.name,
                    "material_path": material.material_path,
                    "extension_type": material.extension_type,
                    "video_duration": material.video_duration,
                    "file_size": material.file_size,
                    "created_at": material.created_at.isoformat() if material.created_at else None,
                    "updated_at": material.updated_at.isoformat() if material.updated_at else None,
                    "file_type": "video" if material.extension_type in ['mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv'] else "document",
                    "processing_status": material.processing_status,
                    "processing_progress": material.processing_progress,
                    "processing_error": material.processing_error,
                    # VdoCipher fields
                    "vdocipher_video_id": material.vdocipher_video_id,
                    "video_status": material.video_status,
                    "video_thumbnail_url": material.video_thumbnail_url,
                    "video_poster_url": material.video_poster_url,
                    "requires_drm": material.requires_drm
                })

        return jsonify({
            "status": "success",
            "device_verification": {
                "is_authorized": is_authorized,
                "message": "Device authorized to access materials" if is_authorized else "Device not authorized to access materials. Please contact administrator.",
                "device_id": device.id,
                "is_primary": device.is_primary,
                "last_used": device.last_used.isoformat() if device.last_used else None
            },
            "data": {
                "items": serialized_materials,
                "total": total if is_authorized else 0,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# REMOVED: Old upload endpoint - replaced with streamlined version below

@subtopic_materials_bp.route('/study-materials/subtopic-materials/upload', methods=['POST'])
@jwt_required()
def upload_material():
    """
    Streamlined video upload endpoint with 2-process system:
    1. Convert video to HLS segments (processing status)
    2. Migrate HLS to B2 storage (archiving status)
    """
    try:
        print("Starting streamlined video upload process...")
        
        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        subtopic_id = request.form.get('subtopic_id')
        material_category_id = request.form.get('material_category_id')
        name = request.form.get('name')
        video_duration = request.form.get('video_duration')
        
        # Validate required fields
        if not all([file, subtopic_id, material_category_id, name]):
            return jsonify({"error": "Missing required fields"}), 400
        
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
        # Get form data
        current_user_id = get_jwt_identity()
        extension_type = file.filename.rsplit('.', 1)[1].lower()
        
        # Only allow video files for HLS
        if extension_type not in ['mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv']:
            return jsonify({"error": "Only video files are allowed for HLS conversion"}), 400
        
        # Get category code
        category = db_session.query(StudyMaterialCategory)\
            .filter(StudyMaterialCategory.id == int(material_category_id))\
            .first()
            
        if not category:
            return jsonify({"error": "Material category not found"}), 404
        
        # Create temporary file for processing
        current_date = datetime.now()
        video_id = str(uuid.uuid4())
        
        # Create filename using material name
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name)
        timestamp = current_date.strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{safe_name}_{timestamp}.{extension_type}"
        
        # Create temp directory for processing
        temp_dir = os.path.join(UPLOAD_FOLDER, 'temp', video_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save original file to temp location
        temp_file_path = os.path.join(temp_dir, unique_filename)
        file.save(temp_file_path)
        
        # Get file size
        file_size = os.path.getsize(temp_file_path)
        
        # Handle video duration
        try:
            if video_duration and ':' in video_duration:
                video_duration = convert_time_to_seconds(video_duration)
            else:
                video_duration = float(video_duration) if video_duration is not None else None
        except Exception as e:
            video_duration = None
        
        # Create material record
        material_data = SubtopicMaterialCreate(
            subtopic_id=int(subtopic_id),
            material_category_id=int(material_category_id),
            name=name,
            material_path=f"temp/{video_id}/{unique_filename}",  # Temporary path
            extension_type=extension_type,
            file_size=file_size,
            video_duration=video_duration,
            processing_status='pending',
            processing_progress=0,
            created_by=int(current_user_id),
            updated_by=int(current_user_id)
        )
        
        # Create material record (temporary path; will be updated by background local HLS conversion)
        material = SubtopicMaterial(**material_data.dict())
        db_session.add(material)
        db_session.commit()
        
        # Queue the streamlined HLS conversion task
        print("\n" + "="*50)
        print(f"🎬 QUEUING STREAMLINED VIDEO PROCESSING")
        print(f"📝 Material ID: {material.id}")
        print(f"📁 Temp file: {temp_file_path}")
        print(f"🆔 Video ID: {video_id}")
        print(f"📂 Category: {category.code}")
        print("="*50 + "\n")
        
        # Import the streamlined task
        from tasks_streamlined import convert_video_to_hls_task
        
        # Queue the HLS conversion task (local-only; B2 migration disabled)
        try:
            convert_video_to_hls_task.apply_async(
                args=[material.id, temp_file_path, video_id, category.code],
                queue='video_processing'
            )
            
            return jsonify({
                "status": "success",
                "message": "Video upload started. Processing in background and stored locally.",
                "data": {
                    "id": material.id,
                    "name": material.name,
                    "material_path": material.material_path,
                    "extension_type": material.extension_type,
                    "file_size": material.file_size,
                    "video_duration": material.video_duration,
                    "created_at": material.created_at.isoformat(),
                    "updated_at": material.updated_at.isoformat(),
                    "processing_status": material.processing_status,
                    "processing_progress": material.processing_progress
                }
            })
        except Exception as celery_error:
            # If Celery/Redis connection fails, update material status and return error
            print(f"Failed to queue Celery task: {str(celery_error)}")
            material.processing_status = 'failed'
            material.processing_error = f"Task queue unavailable: {str(celery_error)}"
            db_session.commit()
            
            # Clean up temp file
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            
            return jsonify({
                "error": "Video processing service is currently unavailable. Please ensure Redis and Celery worker are running.",
                "details": str(celery_error)
            }), 503
        
    except Exception as e:
        print(f"Error in upload_material: {str(e)}")
        # Clean up material record if it was created
        if 'material' in locals() and material.id:
            try:
                db_session.delete(material)
                db_session.commit()
            except Exception:
                pass
        # Clean up temp file
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
        return jsonify({"error": str(e)}), 500

# New: Documents upload endpoint (PDFs only)
@subtopic_materials_bp.route('/study-materials/subtopic-materials/upload-docs', methods=['POST'])
@jwt_required()
def upload_document_material():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        subtopic_id = request.form.get('subtopic_id')
        material_category_id = request.form.get('material_category_id')
        name = request.form.get('name')

        if not all([file, subtopic_id, material_category_id, name]):
            return jsonify({"error": "Missing required fields"}), 400

        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext != 'pdf':
            return jsonify({"error": "Only PDF documents are allowed"}), 400

        # Ensure category exists
        category = db_session.query(StudyMaterialCategory) \
            .filter(StudyMaterialCategory.id == int(material_category_id)) \
            .first()
        if not category:
            return jsonify({"error": "Material category not found"}), 404

        # Build storage path under uploads/documents/<YYYY>/<MM>/<uuid>/<filename>
        now = datetime.now()
        doc_uuid = str(uuid.uuid4())
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name)
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_name}_{timestamp}.pdf"

        relative_dir = os.path.join('documents', f"{now.year}", f"{now.month:02d}", doc_uuid)
        absolute_dir = os.path.join(UPLOAD_FOLDER, relative_dir)
        os.makedirs(absolute_dir, exist_ok=True)

        absolute_path = os.path.join(absolute_dir, filename)
        file.save(absolute_path)

        file_size = os.path.getsize(absolute_path)
        relative_path = os.path.join(relative_dir, filename).replace('\\', '/')

        current_user_id = get_jwt_identity()

        # Create material row as completed (no background processing for PDFs)
        material_data = SubtopicMaterialCreate(
            subtopic_id=int(subtopic_id),
            material_category_id=int(material_category_id),
            name=name,
            material_path=relative_path,
            extension_type='pdf',
            file_size=file_size,
            video_duration=None,
            processing_status='completed',
            processing_progress=100,
            created_by=int(current_user_id),
            updated_by=int(current_user_id)
        )

        material = SubtopicMaterial(**material_data.dict())
        db_session.add(material)
        db_session.commit()

        return jsonify({
            "status": "success",
            "message": "Document uploaded successfully.",
            "data": {
                "id": material.id,
                "name": material.name,
                "material_path": material.material_path,
                "extension_type": material.extension_type,
                "file_size": material.file_size,
                "created_at": material.created_at.isoformat() if material.created_at else None,
                "updated_at": material.updated_at.isoformat() if material.updated_at else None,
                "processing_status": material.processing_status,
                "processing_progress": material.processing_progress
            }
        }), 201
    except Exception as e:
        logger.error(f"Error in upload_document_material: {str(e)}")
        db_session.rollback()
        return jsonify({"error": str(e)}), 500

# REMOVED: Old upload endpoints to eliminate chaos
# Only the streamlined /upload endpoint remains
    try:
        print("Starting B2 HLS upload process...")
        # Check if the post request has the file part
        if 'file' not in request.files:
            print("No file part in request")
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        subtopic_id = request.form.get('subtopic_id')
        material_category_id = request.form.get('material_category_id')
        name = request.form.get('name')
        video_duration = request.form.get('video_duration')
        
        print(f"Received file: {file.filename}")
        print(f"Form data: subtopic_id={subtopic_id}, material_category_id={material_category_id}, name={name}")
        
        # Validate required fields
        if not all([file, subtopic_id, material_category_id, name]):
            print("Missing required fields")
            return jsonify({"error": "Missing required fields"}), 400
        
        if file.filename == '':
            print("No selected file")
            return jsonify({"error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            print(f"File type not allowed: {file.filename}")
            return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
            
        # Get form data
        current_user_id = get_jwt_identity()
        print(f"Current user ID: {current_user_id}")
        
        # Get file extension
        extension_type = file.filename.rsplit('.', 1)[1].lower()
        print(f"File extension: {extension_type}")
        
        # Only allow video files for HLS
        if extension_type not in ['mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv']:
            print(f"Invalid file type for HLS: {extension_type}")
            return jsonify({"error": "Only video files are allowed for HLS conversion"}), 400
        
        # Get category code
        category = db_session.query(StudyMaterialCategory)\
            .filter(StudyMaterialCategory.id == int(material_category_id))\
            .first()
            
        if not category:
            print(f"Material category not found: {material_category_id}")
            return jsonify({"error": "Material category not found"}), 404
        
        # Generate unique ID for the video
        video_id = str(uuid.uuid4())
        
        # Create temporary file for processing
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension_type}")
        temp_file_path = temp_file.name
        
        try:
            # Save uploaded file to temporary location
            file.save(temp_file_path)
            print(f"Saved uploaded file to temporary location: {temp_file_path}")
        except Exception as e:
            print(f"Error saving uploaded file: {str(e)}")
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            return jsonify({"error": f"Failed to save uploaded file: {str(e)}"}), 500
        
        # Get file size
        try:
            file_size = os.path.getsize(temp_file_path)
            print(f"File size: {file_size} bytes")
        except Exception as e:
            print(f"Error getting file size: {str(e)}")
            file_size = 0
        
        # Handle video duration
        try:
            if video_duration and ':' in video_duration:
                video_duration = convert_time_to_seconds(video_duration)
            else:
                video_duration = float(video_duration) if video_duration is not None else None
            print(f"Video duration: {video_duration} seconds")
        except Exception as e:
            print(f"Error processing video duration: {str(e)}")
            video_duration = None
        
        # Create B2 path for the material
        current_date = datetime.now()
        b2_material_path = f"hls/{category.code}/{current_date.year}/{current_date.month:02d}/{video_id}/output.m3u8"
        
        # Create material record with B2 path
        material_data = SubtopicMaterialCreate(
            subtopic_id=int(subtopic_id),
            material_category_id=int(material_category_id),
            name=name,
            material_path=b2_material_path.replace('\\', '/'),
            extension_type='m3u8',  # Store as m3u8 since we're using HLS
            file_size=file_size,
            video_duration=video_duration,
            processing_status='pending',  # Set initial status
            processing_progress=0,  # Set initial progress
            created_by=int(current_user_id),
            updated_by=int(current_user_id)
        )
        
        # Create material record
        material = SubtopicMaterial(**material_data.dict())
        db_session.add(material)
        db_session.commit()
        
        # Queue the B2 HLS conversion task
        print("\n" + "="*50)
        print(f"🎬 QUEUING B2 VIDEO PROCESSING TASK")
        print(f"📝 Material ID: {material.id}")
        print(f"📁 Temp file path: {temp_file_path}")
        print(f"🆔 Video ID: {video_id}")
        print(f"📂 Category code: {category.code}")
        print("="*50 + "\n")
        
        # Queue the task with the video_processing queue
        try:
            process_video_b2.apply_async(
                args=[material.id, temp_file_path, video_id, category.code],
                queue='video_processing'
            )
            
            return jsonify({
                "status": "success",
                "message": "Video upload started. Processing in background with B2 storage.",
                "data": {
                    "id": material.id,
                    "name": material.name,
                    "material_path": material.material_path,
                    "extension_type": material.extension_type,
                    "file_size": material.file_size,
                    "video_duration": material.video_duration,
                    "created_at": material.created_at.isoformat(),
                    "updated_at": material.updated_at.isoformat(),
                    "processing_status": material.processing_status,
                    "processing_progress": material.processing_progress
                }
            })
        except Exception as celery_error:
            # If Celery/Redis connection fails, update material status and return error
            print(f"Failed to queue Celery task: {str(celery_error)}")
            material.processing_status = 'failed'
            material.processing_error = f"Task queue unavailable: {str(celery_error)}"
            db_session.commit()
            
            # Clean up temp file
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            
            return jsonify({
                "error": "Video processing service is currently unavailable. Please ensure Redis and Celery worker are running.",
                "details": str(celery_error)
            }), 503
        
    except Exception as e:
        print(f"Error in upload_material_hls_b2: {str(e)}")
        # Clean up material record if it was created
        if 'material' in locals() and material.id:
            try:
                db_session.delete(material)
                db_session.commit()
            except Exception:
                pass
        # Clean up temp file if it exists
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
        return jsonify({"error": str(e)}), 500

# REMOVED: Old upload-hls-local endpoint - replaced with streamlined version

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>', methods=['GET'])
@jwt_required()
def get_material(material_id):
    try:
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
            
        return jsonify({
            "id": material.id,
            "subtopic_id": material.subtopic_id,
            "material_category_id": material.material_category_id,
            "name": material.name,
            "material_path": material.material_path,
            "b2_material_path": getattr(material, 'b2_material_path', None),
            "storage_location": getattr(material, 'storage_location', 'local'),
            "extension_type": material.extension_type,
            "created_at": material.created_at.isoformat() if material.created_at else None,
            "updated_at": material.updated_at.isoformat() if material.updated_at else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>', methods=['PUT'])
@jwt_required()
def update_material(material_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        data['updated_by'] = int(current_user_id)
        
        material_data = SubtopicMaterialUpdate(**data)
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
            
        # If subtopic_id is being updated, verify the new subtopic exists
        if material_data.subtopic_id is not None:
            subtopic = db_session.query(SubTopic).filter(
                SubTopic.id == material_data.subtopic_id,
                SubTopic.is_active == True
            ).first()
            if not subtopic:
                return jsonify({"error": "New subtopic not found"}), 404
            
        for field, value in material_data.dict(exclude_unset=True).items():
            setattr(material, field, value)
            
        db_session.commit()
        db_session.refresh(material)
        
        return jsonify({
            "id": material.id,
            "subtopic_id": material.subtopic_id,
            "material_category_id": material.material_category_id,
            "name": material.name,
            "material_path": material.material_path,
            "extension_type": material.extension_type,
            "created_at": material.created_at.isoformat() if material.created_at else None,
            "updated_at": material.updated_at.isoformat() if material.updated_at else None
        })
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>', methods=['DELETE'])
@jwt_required()
def delete_material(material_id):
    try:
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
        
        # Delete VdoCipher video if this is a DRM-protected video
        if material.vdocipher_video_id and material.requires_drm:
            try:
                from services.vdocipher_service import VdoCipherService
                vdocipher = VdoCipherService()
                vdocipher.delete_video(material.vdocipher_video_id)
                logger.info(f"✅ Deleted VdoCipher video {material.vdocipher_video_id} for material {material_id}")
            except Exception as vdo_err:
                logger.warning(f"Failed to delete VdoCipher video {material.vdocipher_video_id}: {vdo_err}")
                # Continue with material deletion even if VdoCipher deletion fails
            
        # Attempt filesystem cleanup before deleting DB row
        try:
            path_value = (material.material_path or '').replace('\\', '/')
            storage_location = getattr(material, 'storage_location', 'local')

            # Helper: safely remove a file or directory tree if it exists
            def safe_remove(path_to_remove):
                try:
                    if os.path.isdir(path_to_remove):
                        shutil.rmtree(path_to_remove, ignore_errors=True)
                    elif os.path.isfile(path_to_remove):
                        os.remove(path_to_remove)
                except Exception as _fs_err:
                    logger.warning(f"Failed to remove path {path_to_remove}: {_fs_err}")

            # If this material produced local HLS, remove its folder
            # Expect structure: storage/uploads/hls/<CATEGORY>/<YYYY>/<MM>/<uuid>/output.m3u8
            if storage_location == 'local' and path_value.endswith('output.m3u8'):
                try:
                    manifest_abs = path_value
                    if not manifest_abs.startswith('storage/'):
                        manifest_abs = os.path.join(UPLOAD_FOLDER, path_value)
                    # Parent directory that contains manifest and segments
                    hls_dir = os.path.dirname(manifest_abs)
                    # Extra safety: ensure we're inside uploads/hls
                    if os.path.abspath(hls_dir).startswith(os.path.abspath(os.path.join(UPLOAD_FOLDER, 'hls'))):
                        safe_remove(hls_dir)
                except Exception as _hls_err:
                    logger.warning(f"Error removing HLS folder for material {material_id}: {_hls_err}")

            # If a temp upload directory exists for this material, remove it as well
            # Detect uuid from temp path: temp/<uuid>/...
            try:
                m = re.search(r"temp/([a-f0-9\-]{36})/", path_value, re.IGNORECASE)
                if m:
                    uuid_part = m.group(1)
                    temp_dir = os.path.join(UPLOAD_FOLDER, 'temp', uuid_part)
                    if os.path.abspath(temp_dir).startswith(os.path.abspath(os.path.join(UPLOAD_FOLDER, 'temp'))):
                        safe_remove(temp_dir)
            except Exception as _tmp_err:
                logger.warning(f"Error removing temp folder for material {material_id}: {_tmp_err}")
        except Exception as _cleanup_err:
            logger.warning(f"Cleanup error for material {material_id}: {_cleanup_err}")

        # Finally, delete the DB row
        db_session.delete(material)
        db_session.commit()
        
        return jsonify({"message": "Material deleted successfully"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/view', methods=['GET'])
@jwt_required()
def view_material(material_id):
    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
            
        # Decide path based on storage location
        storage_location = getattr(material, 'storage_location', 'local')
        effective_path = material.material_path if storage_location == 'local' else getattr(material, 'b2_material_path', material.material_path)
        # Get the file path (local only)
        if storage_location == 'local':
            # If path already starts with 'storage/', use it directly
            if effective_path.startswith('storage/'):
                file_path = effective_path
            else:
                file_path = os.path.join(UPLOAD_FOLDER, effective_path)
        else:
            file_path = None
        
        # Check existence or route to B2 if not local
        if storage_location == 'local':
            if not os.path.exists(file_path):
                print(f"File not found at path: {file_path}")
                return jsonify({"error": "File not found"}), 404
        else:
            # For B2-stored files, provide a redirect URL
            try:
                from storage.b2_storage_service import B2StorageService
                b2 = B2StorageService()
                b2_url = b2.get_file_url(effective_path)
                return jsonify({
                    "redirect": b2_url,
                    "type": "b2_download" if material.extension_type.lower() != 'm3u8' else "hls_b2"
                })
            except Exception as e:
                print(f"B2 URL generation failed: {str(e)}")
                return jsonify({"error": "File not found"}), 404
            
        # Determine type; prefer actual file path extension for HLS
        path_ext = os.path.splitext(effective_path)[1].lower()
        is_hls = path_ext == '.m3u8' or material.extension_type.lower() == 'm3u8'
        is_video = material.extension_type.lower() in ['mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv'] and not is_hls
        is_audio = material.extension_type.lower() == 'wav'
        is_pdf = material.extension_type.lower() == 'pdf'
        
        print(f"Attempting to view file: {file_path}")
        print(f"File type: {'video' if is_video else 'audio' if is_audio else 'pdf' if is_pdf else 'hls' if is_hls else 'other'}")
        print(f"File exists: {os.path.exists(file_path)}")
        print(f"File size: {os.path.getsize(file_path)}")
        print(f"File permissions: {oct(os.stat(file_path).st_mode)[-3:]}")
        
        # For HLS files, redirect to the streaming endpoint
        if is_hls and storage_location == 'local':
            return jsonify({
                "redirect": f"/api/study-materials/subtopic-materials/{material_id}/stream",
                "type": "hls"
            })
        
        # Common parameters for send_file
        common_params = {
            'path_or_file': file_path,
            'conditional': True,
            'download_name': os.path.basename(material.material_path)
        }
        
        # For video files, we'll stream the file
        if is_video:
            return send_file(
                **common_params,
                mimetype=f'video/{material.extension_type}'
            )
        elif is_audio:
            # For audio files, we'll send them as attachments
            return send_file(
                **common_params,
                mimetype=f'audio/{material.extension_type}',
                as_attachment=True
            )
        elif is_pdf:
            # For PDF files, we'll send them with the correct MIME type
            return send_file(
                **common_params,
                mimetype='application/pdf',
                as_attachment=False
            )
        else:
            # For other files, we'll send them as attachments
            return send_file(
                **common_params,
                as_attachment=True
            )
            
    except Exception as e:
        print(f"Error in view_material: {str(e)}")
        print(f"Material ID: {material_id}")
        if 'material' in locals():
            print(f"Material path: {material.material_path if material else 'N/A'}")
        return jsonify({"error": str(e)}), 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/stream-old', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def stream_hls_material_old(material_id):
    """
    Endpoint for serving the HLS manifest file.
    Returns a properly formatted M3U8 playlist with absolute segment URLs.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = current_app.response_class(status=204)
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # Check if this is an m3u8 file (prefer path extension)
        effective_ext = os.path.splitext(material.material_path or '')[1].lower()
        is_hls = effective_ext == '.m3u8' or material.extension_type.lower() == 'm3u8'
        print(f"DEBUG LOCAL: material_path={material.material_path}, effective_ext={effective_ext}, extension_type={material.extension_type}, is_hls={is_hls}")
        if not is_hls:
            print(f"Not an HLS stream (ext={material.extension_type}, path_ext={effective_ext})")
            return jsonify({"error": "Not an HLS stream"}), 400
            
        # Get the base directory of the HLS content
        file_path = os.path.join(UPLOAD_FOLDER, material.material_path)
        
        if not os.path.exists(file_path):
            print(f"Playlist not found: {file_path}")
            return jsonify({"error": "Playlist not found"}), 404
            
        print(f"Serving playlist: {file_path}")
        
        # Read the manifest content
        with open(file_path, 'r') as f:
            m3u8_content = f.read()
        
        # Get the base URL for segments
        base_url = request.host_url.rstrip('/')
        segment_base_url = f"{base_url}/api/study-materials/subtopic-materials/{material_id}/segment/"
        
        # Process the manifest content and normalize as VOD
        lines = m3u8_content.split('\n')
        lines = normalize_vod_manifest(lines)
        processed_lines = []
        
        for line in lines:
            if line.startswith('#') or line.strip() == '':
                # Keep tags and comments as is
                processed_lines.append(line)
            else:
                # Convert segment URLs to absolute URLs
                segment_url = f"{segment_base_url}{line}"
                processed_lines.append(segment_url)
        
        # Join the lines back together
        processed_manifest = '\n'.join(processed_lines)
        
        # Create response with modified content
        response = current_app.response_class(
            response=processed_manifest,
            status=200,
            mimetype='application/vnd.apple.mpegurl'
        )
        
        # Add CORS headers for playlist
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        
        return response
            
    except Exception as e:
        print(f"Error in stream_hls_material: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print(f"Material ID: {material_id}")
        if 'material' in locals():
            print(f"Material path: {material.material_path if material else 'N/A'}")
        response = jsonify({"error": str(e)})
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/segment/<path:segment>', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def stream_hls_segment(material_id, segment):
    """
    Endpoint for serving individual HLS segments.
    Returns the .ts file with proper content type and CORS headers.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = current_app.response_class(status=204)
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # Get the base directory of the HLS content
        file_path = os.path.join(UPLOAD_FOLDER, material.material_path)
        hls_dir = os.path.dirname(file_path)
        
        # Serve the segment
        segment_path = os.path.join(hls_dir, segment)
        
        if not os.path.exists(segment_path):
            print(f"Segment not found: {segment_path}")
            return jsonify({"error": "Segment not found"}), 404
            
        print(f"Serving segment: {segment_path}")
        response = send_file(
            path_or_file=segment_path,
            mimetype='video/MP2T'
        )
        
        # Add CORS headers for segments
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        
        return response
            
    except Exception as e:
        print(f"Error in stream_hls_segment: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print(f"Material ID: {material_id}, Segment: {segment}")
        if 'material' in locals():
            print(f"Material path: {material.material_path if material else 'N/A'}")
        response = jsonify({"error": str(e)})
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/segment/<path:segment_file>', methods=['GET'])
def serve_hls_segment(material_id, segment_file):
    """
    Serve individual HLS segments without requiring JWT authentication.
    This is necessary because the HLS player will request segments directly.
    """
    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
            
        # Get the base directory of the HLS content
        main_file_path = os.path.join(UPLOAD_FOLDER, material.material_path)
        hls_dir = os.path.dirname(main_file_path)
        
        # Full path to the segment file
        segment_path = os.path.join(hls_dir, segment_file)
        
        # Basic path validation to prevent directory traversal attacks
        if not os.path.abspath(segment_path).startswith(os.path.abspath(hls_dir)):
            print(f"Security warning: Attempted path traversal: {segment_path}")
            return jsonify({"error": "Invalid segment path"}), 403
        
        if not os.path.exists(segment_path):
            print(f"Segment not found: {segment_path}")
            return jsonify({"error": "Segment not found"}), 404
            
        print(f"Serving segment: {segment_path}")
        response = send_file(
            path_or_file=segment_path,
            mimetype='video/mp2t' if segment_file.endswith('.ts') else 'application/octet-stream'
        )
        
        # Add CORS headers
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        
        return response
        
    except Exception as e:
        print(f"Error in serve_hls_segment: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/segment/<path:segment_file>', methods=['OPTIONS'])
def serve_segment_options(material_id, segment_file):
    """Handle OPTIONS requests for CORS preflight for segment requests"""
    response = jsonify({'message': 'OK'})
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
    response.headers['Access-Control-Max-Age'] = '3600'  # Cache preflight response for 1 hour
    return response

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/status', methods=['GET'])
@jwt_required()
def get_material_status(material_id):
    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
            
        return jsonify({
            "status": "success",
            "data": {
                "id": material.id,
                "name": material.name,
                "processing_status": material.processing_status,
                "processing_progress": material.processing_progress,
                "processing_error": material.processing_error,
                "updated_at": material.updated_at.isoformat() if material.updated_at else None
            }
        })
        
    except Exception as e:
        print(f"Error getting material status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/view-document', methods=['GET'])
@jwt_required()
def view_document(material_id):
    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
            
        # Check if this is a document
        if material.extension_type.lower() not in ['pdf', 'doc', 'docx', 'txt']:
            return jsonify({"error": "Not a document file"}), 400
            
        # Get the file path
        file_path = os.path.join(UPLOAD_FOLDER, material.material_path)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
            
        # Get file metadata
        file_size = os.path.getsize(file_path)
        page_count = None
        is_protected = False
        
        # Get page count for PDFs
        if material.extension_type.lower() == 'pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    page_count = len(pdf_reader.pages)
                    # Check if PDF is encrypted/protected
                    is_protected = pdf_reader.is_encrypted
            except Exception as e:
                print(f"Error reading PDF metadata: {str(e)}")
        
        # Generate document URL
        document_url = f"/api/study-materials/subtopic-materials/{material_id}/view"
        
        # Generate access token if document is protected
        access_token = None
        if is_protected:
            # Generate a temporary access token
            access_token = create_access_token(
                identity=get_jwt_identity(),
                additional_claims={'material_id': material_id},
                expires_delta=timedelta(hours=1)
            )
        
        response_data = {
            "status": "success",
            "data": {
                "document_url": document_url,
                "document_type": material.extension_type.lower(),
                "metadata": {
                    "page_count": page_count,
                    "file_size": file_size,
                    "is_protected": is_protected
                }
            }
        }
        
        # Add access token if document is protected
        if access_token:
            response_data["data"]["access_token"] = access_token
        
        return jsonify(response_data)
            
    except Exception as e:
        print(f"Error in view_document: {str(e)}")
        print(f"Material ID: {material_id}")
        if 'material' in locals():
            print(f"Material path: {material.material_path if material else 'N/A'}")
        return jsonify({"error": str(e)}), 500

# Retry a failed video processing task
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/retry', methods=['POST'])
@jwt_required()
def retry_material_processing(material_id):
    try:
        # Load material
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()

        if not material:
            return jsonify({"error": "Material not found"}), 404

        status = (material.processing_status or '').lower()
        ext = (material.extension_type or '').lower()
        current_path = material.material_path or ''

        # Only allow retry for non-completed items
        if status == 'completed':
            return jsonify({"error": "Material already completed"}), 400

        if status not in ('failed', 'pending', 'error'):
            return jsonify({"error": f"Material not eligible for retry (status={material.processing_status})"}), 400

        # Validate it's a video upload (mp4 etc.) and we still have the temp source
        if ext not in ['mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv']:
            return jsonify({"error": "Only video materials can be retried"}), 400

        # If DB points to HLS and output exists, finalize instead of retrying
        if current_path.lower().endswith('.m3u8'):
            # Resolve absolute path and allow finalize if manifest exists (even if segments check fails)
            abs_manifest = current_path
            if not os.path.isabs(abs_manifest):
                if abs_manifest.startswith('storage/'):
                    abs_manifest = os.path.join(os.getcwd(), abs_manifest)
                else:
                    abs_manifest = os.path.join(UPLOAD_FOLDER, abs_manifest)
            if os.path.exists(abs_manifest) or is_hls_ready(current_path):
                try:
                    material.processing_status = 'completed'
                    material.processing_progress = 100
                    if hasattr(material, 'processing_error'):
                        material.processing_error = None
                    db_session.commit()
                    return jsonify({
                        "message": "HLS already complete; finalized status",
                        "material_id": material.id,
                        "status": material.processing_status,
                        "material_path": material.material_path
                    }), 200
                except Exception as fin_err:
                    db_session.rollback()
                    return jsonify({"error": f"Failed to finalize: {fin_err}"}), 500

        # Locate temp source mp4
        # Case 1: material_path is temp mp4
        video_uuid = None
        filename = None
        match_mp4 = re.search(r"temp/([a-f0-9\-]{36})/([^/]+\.(mp4|webm|avi|mov|wmv|mkv))$", current_path, re.IGNORECASE)
        if match_mp4:
            video_uuid = match_mp4.group(1)
            filename = match_mp4.group(2)
        else:
            # Try extracting uuid from HLS path: storage/uploads/hls/.../<uuid>/output.m3u8
            match_hls = re.search(r"/([a-f0-9\-]{36})/output\.m3u8$", current_path, re.IGNORECASE)
            if match_hls:
                video_uuid = match_hls.group(1)
                # Find any mp4 under temp/<uuid>
                candidates = glob.glob(os.path.join(UPLOAD_FOLDER, 'temp', video_uuid, '*.mp4'))
                if candidates:
                    filename = os.path.basename(candidates[0])

        if not video_uuid or not filename:
            # If we cannot find temp source but HLS manifest exists, finalize
            if current_path.lower().endswith('.m3u8'):
                abs_manifest = current_path
                if not os.path.isabs(abs_manifest):
                    if abs_manifest.startswith('storage/'):
                        abs_manifest = os.path.join(os.getcwd(), abs_manifest)
                    else:
                        abs_manifest = os.path.join(UPLOAD_FOLDER, abs_manifest)
                if os.path.exists(abs_manifest) or is_hls_ready(current_path):
                    try:
                        material.processing_status = 'completed'
                        material.processing_progress = 100
                        if hasattr(material, 'processing_error'):
                            material.processing_error = None
                        db_session.commit()
                        return jsonify({
                            "message": "HLS exists; finalized despite missing temp source",
                            "material_id": material.id,
                            "status": material.processing_status,
                            "material_path": material.material_path
                        }), 200
                    except Exception as fin2_err:
                        db_session.rollback()
                        return jsonify({"error": f"Failed to finalize: {fin2_err}"}), 500
            return jsonify({"error": "Cannot locate temp source path for retry (no uuid/mp4 found)"}), 404

        abs_temp_path = os.path.join(UPLOAD_FOLDER, 'temp', video_uuid, filename)

        if not os.path.exists(abs_temp_path):
            return jsonify({
                "error": "Temp source file not found",
                "path": abs_temp_path
            }), 404

        # Get category code for output pathing
        category = db_session.query(StudyMaterialCategory) \
            .filter(StudyMaterialCategory.id == int(material.material_category_id)) \
            .first()
        if not category:
            return jsonify({"error": "Material category not found"}), 404

        # Reset state and clear previous error
        try:
            material.processing_status = 'pending'
            material.processing_progress = 0
            if hasattr(material, 'processing_error'):
                material.processing_error = None
            db_session.commit()
        except Exception as upd_err:
            db_session.rollback()
            return jsonify({"error": f"Failed to reset status: {upd_err}"}), 500

        # Queue streamlined HLS conversion
        try:
            from tasks_streamlined import convert_video_to_hls_task
            convert_video_to_hls_task.apply_async(
                args=[material.id, abs_temp_path, video_uuid, category.code],
                queue='video_processing'
            )
        except Exception as q_err:
            return jsonify({"error": f"Failed to queue task: {q_err}"}), 500

        return jsonify({
            "message": "Retry queued",
            "material_id": material.id,
            "status": material.processing_status,
            "progress": material.processing_progress,
            "temp_path": abs_temp_path
        }), 202
    except Exception as e:
        logger.error(f"Error retrying material {material_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

# B2-specific view endpoint
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/view-b2', methods=['GET'])
@jwt_required()
def view_material_b2(material_id):
    """
    View material from B2 storage. For HLS videos, redirects to B2 streaming endpoint.
    For other files, provides B2 download URL.
    """
    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
            
        # Check if this is an HLS video (m3u8 file)
        is_hls = material.extension_type.lower() == 'm3u8'
        
        if is_hls:
            # For HLS videos, redirect to the smart streaming endpoint
            return jsonify({
                "redirect": f"/api/study-materials/subtopic-materials/{material_id}/stream",
                "type": "hls",
                "material_path": material.material_path,
                "message": "HLS video - use smart streaming endpoint for playback"
            })
        else:
            # For other files, provide B2 download URL
            try:
                from storage.b2_storage_service import B2StorageService
                b2_storage = B2StorageService()
                
                # Get B2 download URL
                b2_url = b2_storage.get_file_url(material.material_path)
                
                return jsonify({
                    "type": "download",
                    "material_path": material.material_path,
                    "extension_type": material.extension_type,
                    "b2_download_url": b2_url,
                    "message": "Direct download from B2 storage"
                })
                
            except Exception as b2_error:
                logger.error(f"Error getting B2 URL: {str(b2_error)}")
                return jsonify({
                    "error": "Failed to get B2 download URL",
                    "details": str(b2_error)
                }), 500
            
    except Exception as e:
        logger.error(f"Error in view_material_b2: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Smart streaming endpoint - automatically chooses local or B2 based on storage_location
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/stream', methods=['GET'])
@jwt_required()
def stream_hls_material_smart(material_id):
    """
    Smart streaming endpoint that automatically serves from local or B2 based on storage_location
    """
    # NOTE: CORS is handled by nginx to avoid duplicate headers

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # If completed but path is still mp4, try to resolve final HLS manifest and fix DB
        try:
            path_ext = os.path.splitext(material.material_path or '')[1].lower()
            if (material.processing_status or '').lower() == 'completed' and path_ext == '.mp4':
                import re, glob
                # Extract UUID from temp path: temp/<uuid>/filename.mp4
                match = re.search(r"temp/([a-f0-9\-]{36})/", material.material_path or '', re.IGNORECASE)
                if match:
                    video_uuid = match.group(1)
                    # Find output.m3u8 under storage/uploads/hls/**/<uuid>/
                    search_pattern = os.path.join('storage', 'uploads', 'hls', '**', '**', video_uuid, 'output.m3u8')
                    candidates = glob.glob(search_pattern, recursive=True)
                    if candidates:
                        resolved_manifest = candidates[0]
                        if is_hls_ready(resolved_manifest):
                            # Persist fix in DB
                            try:
                                material.material_path = resolved_manifest.replace('\\', '/')
                                material.storage_location = 'local'
                                db_session.commit()
                                print(f"Fixed material_path to {material.material_path}")
                            except Exception as commit_err:
                                db_session.rollback()
                                print(f"Failed to persist material_path fix: {commit_err}")
                            else:
                                # After confirming HLS ready, delete temp mp4 (only if older than 1 day)
                                try:
                                    original_mp4_path = None
                                    if match:
                                        uuid_part = match.group(1)
                                        mp4_candidates = glob.glob(os.path.join(UPLOAD_FOLDER, 'temp', uuid_part, '*.mp4'))
                                        if mp4_candidates:
                                            original_mp4_path = mp4_candidates[0]
                                    if original_mp4_path and os.path.exists(original_mp4_path):
                                        # Resolve absolute path for age check
                                        abs_mp4 = original_mp4_path if os.path.isabs(original_mp4_path) else os.path.join(os.getcwd(), original_mp4_path)
                                        if is_file_older_than_days(abs_mp4, 1):
                                            os.remove(original_mp4_path)
                                            temp_dir = os.path.dirname(original_mp4_path)
                                            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                                                shutil.rmtree(temp_dir, ignore_errors=True)
                                        else:
                                            print(f"Skipping deletion of recent mp4: {original_mp4_path}")
                                except Exception as del_err:
                                    print(f"Temp mp4 cleanup failed: {del_err}")
                        else:
                            print("HLS not ready; skipping DB path update and temp cleanup")
        except Exception as resolve_err:
            print(f"Resolve HLS path error: {resolve_err}")

        # Check if this is an m3u8 file (prefer path extension)
        effective_ext = os.path.splitext(material.material_path or '')[1].lower()
        is_hls = effective_ext == '.m3u8' or (material.extension_type or '').lower() == 'm3u8'
        print(f"DEBUG: material_path={material.material_path}, effective_ext={effective_ext}, extension_type={material.extension_type}, is_hls={is_hls}")
        if not is_hls:
            print(f"Not an HLS stream (ext={material.extension_type}, path_ext={effective_ext})")
            return jsonify({"error": "Not an HLS stream"}), 400
        
        # Check storage location and route accordingly
        storage_location = getattr(material, 'storage_location', 'local')
        
        print(f"Material {material_id} storage location: {storage_location}")
        
        if storage_location == 'b2':
            # Route to B2 streaming
            print(f"Routing material {material_id} to B2 streaming")
            return stream_hls_material_b2(material_id)
        else:
            # Route to local streaming
            print(f"Routing material {material_id} to local streaming")
            return stream_hls_material_local(material_id)
            
    except Exception as e:
        logger.error(f"Error in smart streaming: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Local streaming endpoint
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/stream-local', methods=['GET'])
@jwt_required(optional=True)
def stream_hls_material_local(material_id):
    """
    Endpoint for serving the HLS manifest file from local storage.
    """
    # NOTE: CORS is handled by nginx to avoid duplicate headers

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # If completed but path is still mp4, try to resolve final HLS manifest and fix DB
        try:
            path_ext = os.path.splitext(material.material_path or '')[1].lower()
            if (material.processing_status or '').lower() == 'completed' and path_ext == '.mp4':
                import re, glob
                match = re.search(r"temp/([a-f0-9\-]{36})/", material.material_path or '', re.IGNORECASE)
                if match:
                    video_uuid = match.group(1)
                    search_pattern = os.path.join('storage', 'uploads', 'hls', '**', '**', video_uuid, 'output.m3u8')
                    candidates = glob.glob(search_pattern, recursive=True)
                    if candidates:
                        resolved_manifest = candidates[0]
                        if is_hls_ready(resolved_manifest):
                            try:
                                material.material_path = resolved_manifest.replace('\\', '/')
                                material.storage_location = 'local'
                                db_session.commit()
                                print(f"Fixed material_path to {material.material_path}")
                            except Exception as commit_err:
                                db_session.rollback()
                                print(f"Failed to persist material_path fix: {commit_err}")
                            else:
                                # After confirming HLS ready, delete temp mp4 (only if older than 1 day)
                                original_mp4_path = None
                                try:
                                    uuid_part = match.group(1)
                                    mp4_candidates = glob.glob(os.path.join(UPLOAD_FOLDER, 'temp', uuid_part, '*.mp4'))
                                    if mp4_candidates:
                                        original_mp4_path = mp4_candidates[0]
                                except Exception:
                                    original_mp4_path = None
                                if original_mp4_path and os.path.exists(original_mp4_path):
                                    try:
                                        abs_mp4 = original_mp4_path if os.path.isabs(original_mp4_path) else os.path.join(os.getcwd(), original_mp4_path)
                                        if is_file_older_than_days(abs_mp4, 1):
                                            os.remove(original_mp4_path)
                                            temp_dir = os.path.dirname(original_mp4_path)
                                            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                                                shutil.rmtree(temp_dir, ignore_errors=True)
                                        else:
                                            print(f"Skipping deletion of recent mp4: {original_mp4_path}")
                                    except Exception as del_err:
                                        print(f"Temp mp4 cleanup failed: {del_err}")
                        else:
                            print("HLS not ready; skipping DB path update and temp cleanup")
        except Exception as resolve_err:
            print(f"Resolve HLS path error: {resolve_err}")

        # Check if this is an m3u8 file (prefer path extension)
        effective_ext = os.path.splitext(material.material_path or '')[1].lower()
        is_hls = effective_ext == '.m3u8' or (material.extension_type or '').lower() == 'm3u8'
        if not is_hls:
            print(f"Not an HLS stream (ext={material.extension_type}, path_ext={effective_ext})")
            return jsonify({"error": "Not an HLS stream"}), 400
        
        # Check if material is stored locally (path starts with 'storage/')
        if not material.material_path.startswith('storage/'):
            print(f"Not a locally-stored material: {material.material_path}")
            return jsonify({"error": "Not a locally-stored material"}), 400
        
        # Construct full local path - material_path already includes 'storage/uploads/hls/...'
        local_path = os.path.join(os.getcwd(), material.material_path)
        
        if not os.path.exists(local_path):
            print(f"Local manifest file not found: {local_path}")
            return jsonify({"error": "Local manifest file not found"}), 404
        
        # Check if manifest needs repair (missing ENDLIST or incomplete segments)
        needs_repair = False
        with open(local_path, 'r') as f:
            content = f.read()
            if '#EXT-X-ENDLIST' not in content:
                needs_repair = True
                print(f"Manifest missing ENDLIST: {local_path}")
        
        # Repair manifest if needed
        if needs_repair:
            local_path = repair_incomplete_manifest(local_path)
        
        # Read and serve the manifest file
        with open(local_path, 'r') as f:
            m3u8_content = f.read()
        
        # Process the manifest content and normalize as VOD, then replace segment paths
        lines = m3u8_content.split('\n')
        lines = normalize_vod_manifest(lines)
        processed_lines = []
        
        for line in lines:
            if line.startswith('#') or line.strip() == '':
                # Keep tags and comments as is
                processed_lines.append(line)
            else:
                # Convert segment filename to our local segment endpoint URL
                segment_filename = line.strip()
                segment_url = f"/api/study-materials/subtopic-materials/{material_id}/segment-local/{segment_filename}"
                processed_lines.append(segment_url)
        
        processed_manifest = '\n'.join(processed_lines)
        
        response = current_app.response_class(
            response=processed_manifest,
            status=200,
            mimetype='application/vnd.apple.mpegurl'
        )
        
        # Add CORS headers
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Content-Type'] = 'application/vnd.apple.mpegurl'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in local streaming: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Local segment endpoint
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/segment-local/<filename>', methods=['GET'])
@jwt_required(optional=True)
def stream_hls_segment_local(material_id, filename):
    """
    Endpoint for serving HLS segment files from local storage.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = current_app.response_class(status=204)
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # Check if this is an m3u8 file (prefer path extension)
        effective_ext = os.path.splitext(material.material_path or '')[1].lower()
        is_hls = effective_ext == '.m3u8' or material.extension_type.lower() == 'm3u8'
        if not is_hls:
            print(f"Not an HLS stream (ext={material.extension_type}, path_ext={effective_ext})")
            return jsonify({"error": "Not an HLS stream"}), 400
        
        # Check if material is stored locally (path starts with 'storage/')
        if not material.material_path.startswith('storage/'):
            print(f"Not a locally-stored material: {material.material_path}")
            return jsonify({"error": "Not a locally-stored material"}), 400
        
        # Construct segment path
        manifest_dir = os.path.dirname(os.path.join(os.getcwd(), material.material_path))
        segment_path = os.path.join(manifest_dir, filename)
        
        if not os.path.exists(segment_path):
            print(f"Local segment file not found: {segment_path}")
            return jsonify({"error": "Local segment file not found"}), 404
        
        # Serve the segment file
        return send_file(
            segment_path,
            mimetype='video/MP2T',
            as_attachment=False
        )
        
    except Exception as e:
        logger.error(f"Error in local segment streaming: {str(e)}")
        return jsonify({"error": str(e)}), 500

# B2-specific streaming endpoints (disabled; fallback to local smart streaming)
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/stream-b2', methods=['GET'])
@jwt_required(optional=True)
def stream_hls_material_b2(material_id):
    """
    Endpoint for serving the HLS manifest file from B2 storage.
    Returns a properly formatted M3U8 playlist with B2 segment URLs.
    """
    # NOTE: CORS is handled by nginx to avoid duplicate headers

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # Check if this is an m3u8 file (prefer path extension)
        effective_ext = os.path.splitext(material.material_path or '')[1].lower()
        is_hls = effective_ext == '.m3u8' or material.extension_type.lower() == 'm3u8'
        if not is_hls:
            print(f"Not an HLS stream (ext={material.extension_type}, path_ext={effective_ext})")
            return jsonify({"error": "Not an HLS stream"}), 400
        
        # Determine B2 path from column, fallback to material_path if legacy
        b2_path = getattr(material, 'b2_material_path', None)
        if not b2_path:
            if material.material_path.startswith('hls/'):
                b2_path = material.material_path
            else:
                print(f"Not a B2-stored material: {material.material_path}")
                return jsonify({"error": "Not a B2-stored material"}), 400
        
        # B2 disabled: route to local smart streaming
        return stream_hls_material_smart(material_id)
        
        # Get B2 base URL for segments
        # Extract the base path from b2 path
        base_path = '/'.join(b2_path.split('/')[:-1])  # Remove 'output.m3u8'
        
        # Process the manifest content to replace segment paths with our segment endpoint URLs
        print("Processing manifest content to replace segment paths...")
        lines = m3u8_content.split('\n')
        processed_lines = []
        
        for i, line in enumerate(lines):
            if line.startswith('#') or line.strip() == '':
                # Keep tags and comments as is
                processed_lines.append(line)
            else:
                # Convert segment filename to our segment endpoint URL
                segment_filename = line.strip()
                
                print(f"Processing segment {i}: {segment_filename}")
                
                # Use backend proxy endpoint to keep bucket private and control headers
                segment_url = f"/api/study-materials/subtopic-materials/{material_id}/segment-b2/{segment_filename}"
                processed_lines.append(segment_url)
                print(f"Segment URL: {segment_url}")
        
        # Join the lines back together
        processed_manifest = '\n'.join(processed_lines)
        
        # Create response with modified content
        response = current_app.response_class(
            response=processed_manifest,
            status=200,
            mimetype='application/vnd.apple.mpegurl'
        )
        
        # Add CORS headers for playlist
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Cache-Control'] = 'public, max-age=60'
        
        return response
            
    except Exception as e:
        print(f"Error in stream_hls_material_b2: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print(f"Material ID: {material_id}")
        if 'material' in locals():
            print(f"Material path: {material.material_path if material else 'N/A'}")
        response = jsonify({"error": str(e)})
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/segment-b2/<path:segment>', methods=['GET'])
@jwt_required(optional=True)
def stream_hls_segment_b2(material_id, segment):
    """
    Endpoint for serving individual HLS segments from B2 storage.
    Downloads segment from B2 and serves it with proper content type and CORS headers.
    """
    # NOTE: CORS is handled by nginx to avoid duplicate headers

    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            print(f"Material not found: {material_id}")
            return jsonify({"error": "Material not found"}), 404
        
        # Determine B2 base path from b2_material_path (fallback to material_path if legacy)
        b2_path = getattr(material, 'b2_material_path', None)
        if not b2_path:
            if material.material_path.startswith('hls/'):
                b2_path = material.material_path
            else:
                print(f"Not a B2-stored material: {material.material_path}")
                return jsonify({"error": "Not a B2-stored material"}), 400

        # B2 disabled: route to local segment endpoint
        return stream_hls_segment_local(material_id, segment)
            
    except Exception as e:
        print(f"Error in stream_hls_segment_b2: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print(f"Material ID: {material_id}, Segment: {segment}")
        if 'material' in locals():
            print(f"Material path: {material.material_path if material else 'N/A'}")
        response = jsonify({"error": str(e)})
        # CORS handled by nginx
        # response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, Content-Range, Accept-Ranges'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 500

# Maintenance endpoint: auto-correct material_path from temp mp4 to final m3u8
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/fix-path', methods=['POST'])
@jwt_required()
def fix_material_path(material_id):
    """
    Auto-correct a material's path when it still points to a temp .mp4.
    Finds the final HLS manifest under storage/uploads/hls/**/<uuid>/output.m3u8,
    updates the database, and returns the corrected path.
    """
    try:
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        if not material:
            return jsonify({"error": "Material not found"}), 404

        current_path = material.material_path or ''
        path_ext = os.path.splitext(current_path)[1].lower()

        # If already m3u8, nothing to do
        if path_ext == '.m3u8':
            return jsonify({
                "material_id": material_id,
                "status": "unchanged",
                "material_path": current_path,
                "storage_location": getattr(material, 'storage_location', 'local')
            })

        # Expecting temp/<uuid>/...mp4
        match = re.search(r"temp/([a-f0-9\-]{36})/", current_path, re.IGNORECASE)
        if not match:
            return jsonify({
                "error": "Cannot extract UUID from current material_path",
                "material_path": current_path
            }), 400

        video_uuid = match.group(1)
        search_pattern = os.path.join('storage', 'uploads', 'hls', '**', '**', video_uuid, 'output.m3u8')
        candidates = glob.glob(search_pattern, recursive=True)
        if not candidates:
            return jsonify({
                "error": "HLS manifest not found",
                "search_pattern": search_pattern,
                "uuid": video_uuid
            }), 404

        resolved_manifest = candidates[0].replace('\\', '/')

        # Only update if HLS output is actually ready
        if not is_hls_ready(resolved_manifest):
            return jsonify({
                "material_id": material_id,
                "status": "pending",
                "message": "HLS not ready; manifest or segments missing",
                "found_manifest": resolved_manifest
            }), 202

        try:
            old_path = material.material_path
            material.material_path = resolved_manifest
            material.storage_location = 'local'
            db_session.commit()
        except Exception as commit_err:
            db_session.rollback()
            return jsonify({"error": f"DB update failed: {commit_err}"}), 500

        # After successful update and readiness, remove temp mp4 if present
        try:
            m = re.search(r"temp/([a-f0-9\-]{36})/", old_path or '', re.IGNORECASE)
            if m:
                uuid_part = m.group(1)
                mp4_candidates = glob.glob(os.path.join(UPLOAD_FOLDER, 'temp', uuid_part, '*.mp4'))
                if mp4_candidates:
                    mp4_path = mp4_candidates[0]
                    try:
                        abs_mp4 = mp4_path if os.path.isabs(mp4_path) else os.path.join(os.getcwd(), mp4_path)
                        if is_file_older_than_days(abs_mp4, 1):
                            if os.path.exists(mp4_path):
                                os.remove(mp4_path)
                            temp_dir = os.path.dirname(mp4_path)
                            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                                shutil.rmtree(temp_dir, ignore_errors=True)
                        else:
                            logger.info(f"Skipping deletion of recent mp4: {mp4_path}")
                    except Exception as del_err:
                        logger.warning(f"Temp mp4 cleanup failed for {material_id}: {del_err}")
        except Exception as e:
            logger.warning(f"Temp cleanup error for {material_id}: {e}")

        return jsonify({
            "material_id": material_id,
            "status": "updated",
            "material_path": material.material_path,
            "storage_location": getattr(material, 'storage_location', 'local')
        })

    except Exception as e:
        logger.error(f"Error in fix_material_path: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Migration endpoints
@subtopic_materials_bp.route('/study-materials/subtopic-materials/<int:material_id>/migrate-to-b2', methods=['POST'])
@jwt_required()
def trigger_migrate_to_b2(material_id):
    """
    Trigger migration of a specific material from local to B2 storage
    """
    try:
        # Get the material from the database
        material = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.id == material_id
        ).first()
        
        if not material:
            return jsonify({"error": "Material not found"}), 404
        
        # Check if material is already in B2
        storage_location = getattr(material, 'storage_location', 'local')
        if storage_location == 'b2':
            return jsonify({
                "message": "Material is already stored in B2",
                "material_id": material_id,
                "storage_location": storage_location
            }), 200
        
        # Check if material is stored locally
        if not material.material_path.startswith('storage/'):
            return jsonify({
                "error": "Material is not stored locally",
                "material_path": material.material_path
            }), 400
        
        # B2 disabled
        return jsonify({
            "message": "B2 migration disabled",
            "material_id": material_id,
            "status": "disabled"
        }), 200
        
    except Exception as e:
        logger.error(f"Error triggering migration: {str(e)}")
        return jsonify({"error": str(e)}), 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/migrate-all-to-b2', methods=['POST'])
@jwt_required()
def trigger_migrate_all_to_b2():
    """
    Trigger migration of all local materials to B2 storage
    """
    try:
        # B2 disabled
        return jsonify({
            "message": "Bulk migration to B2 disabled",
            "status": "disabled"
        }), 200
        
    except Exception as e:
        logger.error(f"Error triggering bulk migration: {str(e)}")
        return jsonify({"error": str(e)}), 500

@subtopic_materials_bp.route('/study-materials/subtopic-materials/migration-status', methods=['GET'])
@jwt_required()
def get_migration_status():
    """
    Get status of materials and their storage locations
    """
    try:
        # Get all materials with their storage locations
        materials = db_session.query(SubtopicMaterial).filter(
            SubtopicMaterial.extension_type == 'm3u8'
        ).all()
        
        status_summary = {
            "total_materials": len(materials),
            "local_materials": 0,
            "b2_materials": 0,
            "materials": []
        }
        
        for material in materials:
            storage_location = getattr(material, 'storage_location', 'local')
            if storage_location == 'local':
                status_summary["local_materials"] += 1
            elif storage_location == 'b2':
                status_summary["b2_materials"] += 1
            
            status_summary["materials"].append({
                "id": material.id,
                "name": material.name,
                "storage_location": storage_location,
                "material_path": material.material_path,
                "processing_status": material.processing_status
            })
        
        return jsonify(status_summary), 200
        
    except Exception as e:
        logger.error(f"Error getting migration status: {str(e)}")
        return jsonify({"error": str(e)}), 500

# List materials that are still on local storage (for selective migration)
@subtopic_materials_bp.route('/study-materials/subtopic-materials/local-materials', methods=['GET'])
@jwt_required()
def list_local_materials():
    try:
        # Optional filters
        only_completed = request.args.get('only_completed', 'true').lower() == 'true'
        only_videos = request.args.get('only_videos', 'true').lower() == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        skip = (page - 1) * per_page

        q = db_session.query(SubtopicMaterial).filter(
            getattr(SubtopicMaterial, 'storage_location') == 'local'
        )

        if only_completed:
            q = q.filter(SubtopicMaterial.processing_status == 'completed')
        if only_videos:
            q = q.filter(SubtopicMaterial.extension_type == 'm3u8')

        total = q.count()
        rows = q.order_by(SubtopicMaterial.id.desc()).offset(skip).limit(per_page).all()

        items = []
        for m in rows:
            items.append({
                "id": m.id,
                "name": m.name,
                "subtopic_id": m.subtopic_id,
                "material_category_id": m.material_category_id,
                "extension_type": m.extension_type,
                "processing_status": m.processing_status,
                "processing_progress": m.processing_progress,
                "material_path": m.material_path,
                "storage_location": getattr(m, 'storage_location', 'local'),
                "b2_material_path": getattr(m, 'b2_material_path', None),
                "video_duration": m.video_duration,
                "file_size": m.file_size,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None
            })

        return jsonify({
            "status": "success",
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        logger.error(f"Error listing local materials: {str(e)}")
        return jsonify({"error": str(e)}), 500