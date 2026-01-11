"""
VdoCipher API Routes
Handles video playback OTP generation and video management
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound, Forbidden
from services.vdocipher_service import VdoCipherService
from studies.models.models import SubtopicMaterial
from auth.models.models import User
from database.db_connector import db_session
import logging
import requests

logger = logging.getLogger(__name__)
vdocipher_bp = Blueprint('vdocipher', __name__)

# Lazy initialization - only create service when needed
_vdocipher_service = None

def get_vdocipher_service():
    """Get or create VdoCipher service instance (lazy initialization)"""
    global _vdocipher_service
    if _vdocipher_service is None:
        try:
            _vdocipher_service = VdoCipherService()
        except ValueError as e:
            logger.warning(f"VdoCipher service not available: {e}")
            _vdocipher_service = None
    return _vdocipher_service


@vdocipher_bp.errorhandler(Exception)
def handle_error(error):
    """Global error handler for vdocipher blueprint"""
    logger.error(f"Error in vdocipher route: {str(error)}", exc_info=True)
    
    if isinstance(error, BadRequest):
        return jsonify({'error': str(error)}), 400
    elif isinstance(error, NotFound):
        return jsonify({'error': 'Resource not found'}), 404
    elif isinstance(error, Forbidden):
        return jsonify({'error': 'Access denied'}), 403
    else:
        return jsonify({'error': 'Internal server error'}), 500


@vdocipher_bp.route('/api/videos/<video_id>/otp', methods=['POST'])
@jwt_required()
def get_video_otp(video_id):
    """
    Generate OTP for VdoCipher video playback
    
    Path Parameters:
        video_id: VdoCipher video ID
    
    Returns:
        {
            "status": "success",
            "data": {
                "otp": "...",
                "playbackInfo": "...",
                "video": {
                    "id": 1,
                    "name": "Introduction to Accounting",
                    "duration": 3600
                }
            }
        }
    """
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        user = db_session.query(User).get(current_user_id)
        
        if not user:
            raise NotFound('User not found')
        
        # Find material by VdoCipher video ID
        material = db_session.query(SubtopicMaterial).filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if not material:
            raise NotFound('Video not found')
        
        # Check video status
        if material.video_status != 'ready':
            return jsonify({
                'error': 'Video is not ready for playback',
                'status': material.video_status,
                'message': 'Video is still processing. Please try again in a few minutes.'
            }), 425  # Too Early status code
        
        # TODO: Add access control check
        # For now, allow all authenticated users (for testing)
        # In production, check if user has enrolled in the course/subject
        # if not user.has_access_to_material(material.id):
        #     raise Forbidden('You do not have access to this video')
        
        # Get user IP address
        ip_address = request.remote_addr
        
        # Generate OTP with user watermark
        vdocipher_service = get_vdocipher_service()
        if not vdocipher_service:
            return jsonify({
                'error': 'VdoCipher service not configured',
                'details': 'VDOCIPHER_API_SECRET not set in environment variables'
            }), 503
        
        try:
            otp_data = vdocipher_service.generate_otp(
                video_id=video_id,
                user_id=user.id,
                user_email=user.email,
                user_name=f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip(),
                ip_address=None  # Set to ip_address for IP restriction
            )
        except Exception as e:
            logger.error(f"Failed to generate OTP for video {video_id}: {str(e)}")
            return jsonify({
                'error': 'Failed to generate video credentials',
                'details': str(e)
            }), 503  # Service Unavailable
        
        # Log video access (optional - for analytics)
        logger.info(f"User {user.id} accessed video {video_id} (Material: {material.id})")
        
        return jsonify({
            'status': 'success',
            'data': {
                'otp': otp_data['otp'],
                'playbackInfo': otp_data['playbackInfo'],
                'video': {
                    'id': material.id,
                    'name': material.name,
                    'duration': int(material.video_duration or 0)
                }
            }
        }), 200
        
    except (NotFound, Forbidden) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_video_otp: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500


@vdocipher_bp.route('/api/videos/<video_id>/status', methods=['GET'])
@jwt_required()
def get_video_status(video_id):
    """
    Get video processing status
    
    Path Parameters:
        video_id: VdoCipher video ID
    
    Returns:
        {
            "status": "success",
            "data": {
                "video_id": "...",
                "status": "ready",
                "duration": 3600,
                "thumbnail": "https://...",
                "poster": "https://..."
            }
        }
    """
    try:
        # Find material
        material = db_session.query(SubtopicMaterial).filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if not material:
            raise NotFound('Video not found')
        
        # Get latest status from VdoCipher
        vdocipher_service = get_vdocipher_service()
        if not vdocipher_service:
            return jsonify({
                'error': 'VdoCipher service not configured'
            }), 503
        
        try:
            video_data = vdocipher_service.get_video_details(video_id)
            
            # Update database with latest info
            material.video_status = video_data.get('status', 'processing')
            material.video_duration = video_data.get('length', 0)
            material.video_thumbnail_url = video_data.get('thumbnail')
            material.video_poster_url = video_data.get('poster')
            db_session.commit()
            
        except Exception as e:
            logger.error(f"Failed to fetch video details: {str(e)}")
            # Return cached status from database
            pass
        
        return jsonify({
            'status': 'success',
            'data': {
                'video_id': video_id,
                'status': material.video_status,
                'duration': int(material.video_duration or 0),
                'thumbnail': material.video_thumbnail_url,
                'poster': material.video_poster_url
            }
        }), 200
        
    except NotFound:
        raise
    except Exception as e:
        logger.error(f"Error in get_video_status: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to get video status'}), 500


@vdocipher_bp.route('/api/materials/<int:material_id>/video', methods=['GET'])
@jwt_required()
def get_material_video_info(material_id):
    """
    Get video information for a specific material
    
    Path Parameters:
        material_id: Subtopic material ID
    
    Returns:
        {
            "status": "success",
            "data": {
                "material_id": 1,
                "name": "Introduction",
                "has_video": true,
                "video_id": "...",
                "video_status": "ready",
                "duration": 3600,
                "requires_drm": true
            }
        }
    """
    try:
        material = db_session.query(SubtopicMaterial).get(material_id)
        
        if not material:
            raise NotFound('Material not found')
        
        has_video = material.vdocipher_video_id is not None
        
        return jsonify({
            'status': 'success',
            'data': {
                'material_id': material.id,
                'name': material.name,
                'has_video': has_video,
                'video_id': material.vdocipher_video_id,
                'video_status': material.video_status if has_video else None,
                'duration': int(material.video_duration or 0) if has_video else 0,
                'requires_drm': bool(material.requires_drm)
            }
        }), 200
        
    except NotFound:
        raise
    except Exception as e:
        logger.error(f"Error in get_material_video_info: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to get material info'}), 500


@vdocipher_bp.route('/api/study-materials/subtopic-materials/upload-vdocipher', methods=['POST'])
@jwt_required()
def upload_video_to_vdocipher():
    """
    Upload video to VdoCipher and create material record
    
    Form Data:
        video: Video file
        subtopic_id: Subtopic ID
        material_category_id: Material category ID
        name: Material name
        
    Returns:
        {
            "status": "success",
            "data": {
                "material_id": 123,
                "video_id": "abc123",
                "upload_status": "processing",
                "message": "Video uploaded successfully and is being processed"
            }
        }
    """
    try:
        current_user_id = get_jwt_identity()
        
        # Validate file upload
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        video_file = request.files['video']
        
        if video_file.filename == '':
            return jsonify({'error': 'No video file selected'}), 400
        
        # Get form data
        subtopic_id = request.form.get('subtopic_id')
        material_category_id = request.form.get('material_category_id')
        name = request.form.get('name') or video_file.filename
        
        if not subtopic_id or not material_category_id:
            return jsonify({
                'error': 'subtopic_id and material_category_id are required'
            }), 400
        
        # Validate file type (videos only)
        allowed_extensions = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv']
        file_extension = video_file.filename.rsplit('.', 1)[1].lower() if '.' in video_file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({
                'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'
            }), 400
        
        # Get file size
        video_file.seek(0, 2)  # Seek to end
        file_size = video_file.tell()
        video_file.seek(0)  # Reset to beginning
        
        # Check file size limit (5GB for VdoCipher)
        max_size = 5 * 1024 * 1024 * 1024  # 5GB in bytes
        if file_size > max_size:
            return jsonify({
                'error': 'File too large. Maximum size: 5GB'
            }), 400
        
        logger.info(f"Starting VdoCipher upload: {name} ({file_size} bytes)")
        
        # Step 1: Get upload credentials from VdoCipher
        vdocipher_service = get_vdocipher_service()
        if not vdocipher_service:
            return jsonify({
                'error': 'VdoCipher service not configured',
                'details': 'VDOCIPHER_API_SECRET not set in environment variables'
            }), 503
        
        try:
            upload_data = vdocipher_service.upload_video(title=name)
            logger.info(f"VdoCipher upload response keys: {list(upload_data.keys())}")
            
            # VdoCipher returns: clientPayload, uploadLink (or different keys)
            video_id = upload_data.get('videoId') or upload_data.get('clientPayload', {}).get('videoId')
            upload_link = upload_data.get('uploadLink') or upload_data.get('clientPayload', {}).get('uploadLink')
            
            if not video_id or not upload_link:
                logger.error(f"Missing upload data. Response: {upload_data}")
                raise Exception(f"Invalid response from VdoCipher. Keys: {list(upload_data.keys())}")
                
        except Exception as e:
            logger.error(f"Failed to get VdoCipher upload credentials: {str(e)}")
            return jsonify({
                'error': 'Failed to initialize video upload',
                'details': str(e)
            }), 503
        
        # Step 2: Upload video file to VdoCipher S3
        try:
            # Get client payload for S3 upload
            client_payload = upload_data.get('clientPayload', {})
            
            # VdoCipher uses multipart form upload to S3
            # We need to send the file with the fields from clientPayload
            upload_fields = {
                'key': client_payload.get('key'),
                'x-amz-credential': client_payload.get('x-amz-credential'),
                'x-amz-algorithm': client_payload.get('x-amz-algorithm'),
                'x-amz-date': client_payload.get('x-amz-date'),
                'x-amz-signature': client_payload.get('x-amz-signature'),
                'policy': client_payload.get('policy'),
                'success_action_status': '201',
                'success_action_redirect': ''
            }
            
            # Prepare multipart form data
            files = {
                'file': (video_file.filename, video_file, video_file.content_type or 'video/mp4')
            }
            
            # Upload to S3 using POST (not PUT)
            upload_response = requests.post(
                upload_link,
                data=upload_fields,
                files=files,
                timeout=3600  # 1 hour timeout for large files
            )
            
            # S3 returns 201 or 204 on success
            if upload_response.status_code not in [200, 201, 204]:
                raise Exception(f"S3 upload failed with status {upload_response.status_code}: {upload_response.text}")
            
            logger.info(f"Video uploaded to VdoCipher successfully: {video_id}")
            
        except Exception as e:
            logger.error(f"Failed to upload video to VdoCipher: {str(e)}")
            # Try to delete the partially created video from VdoCipher
            try:
                vdocipher_svc = get_vdocipher_service()
                if vdocipher_svc:
                    vdocipher_svc.delete_video(video_id)
            except:
                pass
            
            return jsonify({
                'error': 'Failed to upload video file',
                'details': str(e)
            }), 500
        
        # Step 3: Check video status from VdoCipher
        try:
            video_details = vdocipher_service.get_video_details(video_id)
            actual_video_status = video_details.get('status', 'processing')
            video_duration = video_details.get('length', 0)
            video_thumbnail = video_details.get('thumbnail')
            video_poster = video_details.get('poster')
            
            logger.info(f"VdoCipher video status: {actual_video_status}")
        except Exception as e:
            # If we can't get status, assume processing
            logger.warning(f"Could not fetch video details, assuming processing: {str(e)}")
            actual_video_status = 'processing'
            video_duration = 0
            video_thumbnail = None
            video_poster = None
        
        # Step 4: Create material record in database
        try:
            from studies.models.models import SubtopicMaterial
            
            material = SubtopicMaterial(
                subtopic_id=int(subtopic_id),
                material_category_id=int(material_category_id),
                name=name,
                material_path='',  # Not used for VdoCipher videos
                extension_type='mp4',  # VdoCipher handles conversion
                file_size=file_size,
                vdocipher_video_id=video_id,
                video_status=actual_video_status,  # Use actual status from VdoCipher
                video_duration=video_duration,
                video_thumbnail_url=video_thumbnail,
                video_poster_url=video_poster,
                requires_drm=True,
                processing_status='completed',  # VdoCipher handles processing
                created_by=current_user_id,
                updated_by=current_user_id
            )
            
            db_session.add(material)
            db_session.commit()
            db_session.refresh(material)
            
            logger.info(f"Material created with ID {material.id} for VdoCipher video {video_id}")
            
            return jsonify({
                'status': 'success',
                'data': {
                    'material_id': material.id,
                    'video_id': video_id,
                    'video_status': 'processing',
                    'message': 'Video uploaded successfully and is being processed by VdoCipher'
                }
            }), 201
            
        except Exception as e:
            logger.error(f"Failed to create material record: {str(e)}")
            db_session.rollback()
            
            # Try to delete video from VdoCipher since database insert failed
            try:
                vdocipher_svc = get_vdocipher_service()
                if vdocipher_svc:
                    vdocipher_svc.delete_video(video_id)
            except:
                pass
            
            return jsonify({
                'error': 'Failed to save material record',
                'details': str(e)
            }), 500
        
    except Exception as e:
        logger.error(f"Unexpected error in upload_video_to_vdocipher: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500


@vdocipher_bp.route('/api/study-materials/subtopic-materials/link-vdocipher', methods=['POST'])
@jwt_required()
def link_existing_vdocipher_video():
    """
    Link an existing VdoCipher video (already uploaded in VdoCipher) to a new material.

    This route does NOT upload any video file. It only:
      - validates the provided VdoCipher video ID
      - fetches its details from VdoCipher
      - creates a new `SubtopicMaterial` record linked to that video ID

    Method: POST
    URL: /api/study-materials/subtopic-materials/link-vdocipher

    JSON Body:
        {
            "video_id": "string",               # Required - existing VdoCipher video ID
            "subtopic_id": 123,                 # Required
            "material_category_id": 45,         # Required
            "name": "Optional material name"    # Optional - defaults to video_id if missing
        }

    Returns (201):
        {
            "status": "success",
            "data": {
                "material_id": 123,
                "video_id": "abc123",
                "video_status": "ready",
                "duration": 3600,
                "message": "Video linked successfully to material"
            }
        }
    """
    try:
        current_user_id = get_jwt_identity()

        payload = request.get_json() or {}
        video_id = payload.get('video_id')
        subtopic_id = payload.get('subtopic_id')
        material_category_id = payload.get('material_category_id')
        name = payload.get('name') or video_id

        # Basic validation
        missing_fields = []
        if not video_id:
            missing_fields.append('video_id')
        if not subtopic_id:
            missing_fields.append('subtopic_id')
        if not material_category_id:
            missing_fields.append('material_category_id')

        if missing_fields:
            return jsonify({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }), 400

        # Ensure IDs are integers where expected
        try:
            subtopic_id = int(subtopic_id)
            material_category_id = int(material_category_id)
        except (TypeError, ValueError):
            return jsonify({
                'error': 'subtopic_id and material_category_id must be integers'
            }), 400

        # Get VdoCipher service
        vdocipher_service = get_vdocipher_service()
        if not vdocipher_service:
            return jsonify({
                'error': 'VdoCipher service not configured',
                'details': 'VDOCIPHER_API_SECRET not set in environment variables'
            }), 503

        # Validate that the video exists in VdoCipher and fetch its details
        try:
            video_details = vdocipher_service.get_video_details(video_id)
        except Exception as e:
            # If the video is not found or API call fails, return a clear error
            error_msg = str(e)
            status_code = 400 if 'not found' in error_msg.lower() else 503
            return jsonify({
                'error': 'Failed to validate VdoCipher video',
                'details': error_msg
            }), status_code

        video_status = video_details.get('status', 'processing')
        video_duration = video_details.get('length', 0)
        video_thumbnail = video_details.get('thumbnail')
        video_poster = video_details.get('poster')

        # Create material record linked to the existing VdoCipher video
        try:
            from studies.models.models import SubtopicMaterial

            material = SubtopicMaterial(
                subtopic_id=subtopic_id,
                material_category_id=material_category_id,
                name=name,
                material_path='',
                extension_type='mp4',
                file_size=0,
                vdocipher_video_id=video_id,
                video_status=video_status,
                video_duration=video_duration,
                video_thumbnail_url=video_thumbnail,
                video_poster_url=video_poster,
                requires_drm=True,
                processing_status='completed',
                created_by=current_user_id,
                updated_by=current_user_id
            )

            db_session.add(material)
            db_session.commit()
            db_session.refresh(material)

            logger.info(f"Material {material.id} linked to existing VdoCipher video {video_id}")

            return jsonify({
                'status': 'success',
                'data': {
                    'material_id': material.id,
                    'video_id': video_id,
                    'video_status': video_status,
                    'duration': int(video_duration or 0),
                    'message': 'Video linked successfully to material'
                }
            }), 201

        except Exception as e:
            logger.error(f"Failed to create material record for existing VdoCipher video {video_id}: {str(e)}")
            db_session.rollback()
            return jsonify({
                'error': 'Failed to save material record',
                'details': str(e)
            }), 500

    except Exception as e:
        logger.error(f"Unexpected error in link_existing_vdocipher_video: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500


@vdocipher_bp.route('/api/webhooks/vdocipher', methods=['POST'])
def vdocipher_webhook():
    """
    Handle webhooks from VdoCipher
    This endpoint is called by VdoCipher when video processing completes
    
    Webhook Payload Structure:
    {
        "hookId": "unique_hook_id",
        "event": "video:ready",
        "time": 1762959487638,
        "payload": {
            "id": "video_id",
            "title": "video_title",
            "status": "ready",
            "length": 3600,
            "posters": [...]
        }
    }
    
    Events:
    - video:ready: Video processing completed
    - video:failed: Video processing failed
    - video:deleted: Video was deleted
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        event_type = data.get('event')
        payload = data.get('payload', {})
        
        # Video ID is in payload.id
        video_id = payload.get('id')
        
        if not video_id:
            logger.error(f"Video ID not found in webhook. Data: {data}")
            return jsonify({'error': 'Video ID not provided'}), 400
        
        logger.info(f"Received VdoCipher webhook: {event_type} for video {video_id}")
        
        # Find material by video ID
        material = db_session.query(SubtopicMaterial).filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if not material:
            logger.warning(f"Material not found for VdoCipher video {video_id}")
            return jsonify({'status': 'success', 'message': 'Material not found'}), 200
        
        # Handle different event types
        if event_type == 'video:ready':
            # Video processing completed successfully
            material.video_status = 'ready'
            material.video_duration = payload.get('length', 0)
            
            # Get first poster URL
            posters = payload.get('posters', [])
            if posters and len(posters) > 0:
                material.video_thumbnail_url = posters[0].get('url')
                material.video_poster_url = posters[0].get('url')
            
            logger.info(f"✅ Video {video_id} is ready for material {material.id}")
            
        elif event_type == 'video:failed':
            # Video processing failed
            material.video_status = 'failed'
            error_message = payload.get('error', 'Unknown error')
            
            logger.error(f"❌ Video {video_id} processing failed: {error_message}")
            
        elif event_type == 'video:deleted':
            # Video was deleted from VdoCipher
            material.vdocipher_video_id = None
            material.video_status = None
            
            logger.info(f"🗑️ Video {video_id} was deleted")
        
        # Save changes
        db_session.commit()
        
        logger.info(f"Webhook processed successfully for video {video_id}")
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error handling VdoCipher webhook: {str(e)}", exc_info=True)
        db_session.rollback()
        return jsonify({'error': str(e)}), 500


@vdocipher_bp.route('/api/health/vdocipher', methods=['GET'])
def check_vdocipher_health():
    """
    Health check endpoint for VdoCipher integration
    
    Returns:
        {
            "status": "healthy",
            "vdocipher_api": "reachable",
            "response_time_ms": 150
        }
    """
    import time
    
    try:
        vdocipher_service = get_vdocipher_service()
        if not vdocipher_service:
            return jsonify({
                'status': 'unhealthy',
                'vdocipher_api': 'not_configured',
                'message': 'VDOCIPHER_API_SECRET not set in environment variables'
            }), 503
        
        start_time = time.time()
        
        # Test API connection
        if vdocipher_service.test_connection():
            response_time = (time.time() - start_time) * 1000
            
            return jsonify({
                'status': 'healthy',
                'vdocipher_api': 'reachable',
                'response_time_ms': round(response_time, 2)
            }), 200
        else:
            return jsonify({
                'status': 'degraded',
                'vdocipher_api': 'unreachable'
            }), 503
            
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'vdocipher_api': 'error',
            'error': str(e)
        }), 503

