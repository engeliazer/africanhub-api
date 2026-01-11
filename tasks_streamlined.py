import os
import subprocess
import tempfile
import shutil
import logging
import traceback
import re
from datetime import datetime
from celery import Celery
import pymysql
from storage.b2_storage_service import B2StorageService

# Import celery instance and tasks
from celery_config import celery

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'ocpac',
    'password': 'oCpAc@2025',
    'database': 'ocpac',
    'charset': 'utf8mb4',
    'autocommit': True,
    'port': 3306
}

logger.info(f"Database config - Host: {DB_CONFIG['host']}, User: {DB_CONFIG['user']}, Database: {DB_CONFIG['database']}")

def update_material_status(material_id, status, progress=0, error_message=None):
    """Update material processing status and progress in database"""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        # Auto-complete when progress reaches 100% and try to fix material_path to final m3u8
        if progress == 100 and status == 'processing':
            status = 'completed'
            logger.info(f"🎉 Auto-completing material {material_id} - Progress reached 100%")
            try:
                with connection.cursor() as cursor:
                    # Fetch current path
                    cursor.execute("SELECT material_path FROM subtopic_materials WHERE id = %s", (material_id,))
                    row = cursor.fetchone()
                    current_path = row[0] if row else None
                if current_path and current_path.endswith('.mp4'):
                    import re, glob
                    match = re.search(r"temp/([a-f0-9\-]{36})/", current_path, re.IGNORECASE)
                    if match:
                        video_uuid = match.group(1)
                        search_pattern = os.path.join('storage', 'uploads', 'hls', '**', '**', video_uuid, 'output.m3u8')
                        candidates = glob.glob(search_pattern, recursive=True)
                        if candidates:
                            resolved_manifest = candidates[0].replace('\\', '/')
                            with connection.cursor() as cursor:
                                cursor.execute(
                                    """
                                    UPDATE subtopic_materials
                                    SET material_path = %s, storage_location = %s
                                    WHERE id = %s
                                    """,
                                    (resolved_manifest, 'local', material_id)
                                )
                            logger.info(f"🔧 Fixed material_path for {material_id} to {resolved_manifest}")
            except Exception as path_fix_err:
                logger.error(f"Path auto-fix failed for {material_id}: {path_fix_err}")
        
        with connection.cursor() as cursor:
            sql = """
            UPDATE subtopic_materials 
            SET processing_status = %s, processing_progress = %s, processing_error = %s
            WHERE id = %s
            """
            cursor.execute(sql, (status, progress, error_message, material_id))
        
        logger.info(f"Updated material {material_id} - Status: {status}, Progress: {progress}%")
        
    except Exception as e:
        logger.error(f"Error updating material status: {str(e)}")
        raise
    finally:
        if connection:
            connection.close()

def update_material_path(material_id, material_path, storage_location):
    """Update material path and storage location in database"""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            sql = """
            UPDATE subtopic_materials 
            SET material_path = %s, storage_location = %s
            WHERE id = %s
            """
            cursor.execute(sql, (material_path, storage_location, material_id))
        
        logger.info(f"Updated material {material_id} - Path: {material_path}, Storage: {storage_location}")
        
    except Exception as e:
        logger.error(f"Error updating material path: {str(e)}")
        raise
    finally:
        if connection:
            connection.close()

def get_file_size_mb(file_path):
    """Get file size in MB"""
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception as e:
        logger.error(f"Error getting file size: {str(e)}")
        return 0

def get_material_info(material_id):
    """Get material information from database"""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            sql = """
            SELECT sm.id, sm.name, sm.material_path, sm.processing_status, sm.processing_progress,
                   smc.code as category_code
            FROM subtopic_materials sm
            JOIN study_material_categories smc ON sm.material_category_id = smc.id
            WHERE sm.id = %s
            """
            cursor.execute(sql, (material_id,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'id': result[0],
                    'name': result[1],
                    'material_path': result[2],
                    'processing_status': result[3],
                    'processing_progress': result[4],
                    'category_code': result[5]
                }
            return None
            
    except Exception as e:
        logger.error(f"Error getting material info: {str(e)}")
        return None
    finally:
        if connection:
            connection.close()

def convert_video_to_hls(material_id: int, input_file_path: str, video_id: str, category_code: str):
    """
    Process 1: Convert video to HLS segments
    Status: processing (0-100%)
    """
    logger.info(f"Starting HLS conversion for material {material_id}")
    logger.info(f"Input file: {input_file_path}")
    
    temp_dir = None
    
    try:
        # Check file size
        file_size_mb = get_file_size_mb(input_file_path)
        if file_size_mb > 1200:
            error_msg = f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size of 1200MB"
            logger.error(error_msg)
            update_material_status(material_id, 'failed', 0, error_msg)
            raise ValueError(error_msg)
        
        # Update status to processing
        update_material_status(material_id, 'processing', 0)
        logger.info(f"Updated material {material_id} - Status: processing, Progress: 0%")
        
        # Create final output directory directly (no temp needed)
        current_date = datetime.now()
        local_output_dir = os.path.join('storage', 'uploads', 'hls', category_code, 
                                       str(current_date.year), str(current_date.month).zfill(2), video_id)
        logger.info(f"Creating final output directory: {local_output_dir}")
        try:
            os.makedirs(local_output_dir, exist_ok=True)
            logger.info(f"Final output directory created successfully")
        except Exception as e:
            logger.error(f"Failed to create final output directory: {str(e)}")
            raise
        
        # HLS output path directly in final location
        hls_output_path = os.path.join(local_output_dir, "output.m3u8")
        
        # Set up FFmpeg path - try common locations
        ffmpeg_path = None
        for path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', 'ffmpeg']:
            if path == 'ffmpeg' or os.path.exists(path):
                ffmpeg_path = path
                break
        
        if not ffmpeg_path or (ffmpeg_path != 'ffmpeg' and not os.path.exists(ffmpeg_path)):
            raise RuntimeError(f"FFmpeg not found. Please ensure FFmpeg is installed (tried: /usr/bin/ffmpeg, /usr/local/bin/ffmpeg)")
        
        # Get video duration first
        try:
            duration_cmd = [
                ffmpeg_path,
                '-i', input_file_path,
                '-f', 'null',
                '-'
            ]
            duration_process = subprocess.Popen(
                duration_cmd,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            _, stderr = duration_process.communicate()
            
            # Extract duration from stderr
            duration_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})", stderr)
            if duration_match:
                hours, minutes, seconds = map(int, duration_match.groups())
                total_duration_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
                logger.info(f"Video duration: {hours}:{minutes}:{seconds} ({total_duration_ms}ms)")
            else:
                total_duration_ms = 0
                logger.warning("Could not determine video duration")
        except Exception as e:
            logger.error(f"Error getting video duration: {str(e)}")
            total_duration_ms = 0
        
        # Construct FFmpeg command for HLS conversion
        ffmpeg_cmd = [
            ffmpeg_path,
            '-i', input_file_path,
            '-vf', 'scale=-2:720',  # Scale to 720p while maintaining aspect ratio
            '-c:v', 'libx264',
            '-b:v', '1000k',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-profile:v', 'baseline',
            '-level', '3.0',
            '-hls_time', '10',
            '-hls_list_size', '0',
            '-start_number', '0',
            '-hls_segment_filename', f'{local_output_dir}/segment_%03d.ts',
            '-f', 'hls',
            '-progress', 'pipe:1',  # Output progress to stdout
            hls_output_path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
        
        # Start FFmpeg process
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        last_progress = 0
        # Monitor progress (conversion phase - 0-100%)
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if 'out_time_ms=' in line:
                try:
                    time_str = line.split('=')[1].strip()
                    if time_str != 'N/A' and total_duration_ms > 0:
                        time_ms = int(time_str)
                        conversion_progress = min(int((time_ms / total_duration_ms) * 100), 100)
                        
                        # Only update if progress has changed significantly (every 5%)
                        if conversion_progress > last_progress and (conversion_progress - last_progress) >= 5:
                            last_progress = conversion_progress
                            logger.info(f"Conversion progress: {conversion_progress}%")
                            
                            # Update database progress
                            update_material_status(material_id, 'processing', conversion_progress)
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing progress: {str(e)}")
                    continue
        
        # Wait for process to complete with timeout (58 minutes to allow for soft limit)
        try:
            return_code = process.wait(timeout=3500)  # 58 minutes timeout
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg process timed out after 58 minutes")
            process.kill()
            process.wait()
            raise Exception("FFmpeg process timed out after 58 minutes")
        
        if return_code != 0:
            error_output = process.stderr.read()
            logger.error(f"FFmpeg process failed with return code {return_code}")
            logger.error(f"Error output: {error_output}")
            raise Exception(f"FFmpeg process failed with return code {return_code}")
        
        # Check if HLS files were created
        logger.info(f"Checking if HLS manifest exists: {hls_output_path}")
        if not os.path.exists(hls_output_path):
            logger.error(f"HLS manifest file not found at: {hls_output_path}")
            raise Exception("HLS manifest file was not created")
        
        logger.info(f"HLS manifest file exists: {hls_output_path}")
        
        # Files are already in final location - no copying needed!
        logger.info(f"HLS files created directly in final location: {local_output_dir}")
        
        # Count HLS files for verification
        try:
            hls_files = [f for f in os.listdir(local_output_dir) if f.endswith(('.m3u8', '.ts'))]
            logger.info(f"Found {len(hls_files)} HLS files in final location")
        except Exception as e:
            logger.error(f"Failed to list final directory: {str(e)}")
            raise
        
        # Simple, bulletproof database update
        local_material_path = os.path.join(local_output_dir, 'output.m3u8').replace('\\', '/')
        logger.info(f"Updating material path to: {local_material_path}")
        
        # Try the simplest possible approach first
        try:
            connection = pymysql.connect(**DB_CONFIG)
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE subtopic_materials 
                SET material_path = %s, storage_location = %s, processing_status = %s, processing_progress = %s
                WHERE id = %s
            """, (local_material_path, 'local', 'completed', 100, material_id))
            connection.commit()
            connection.close()
            logger.info(f"✅ HLS conversion completed successfully for material {material_id}")
        except Exception as e:
            logger.error(f"❌ Database update failed: {str(e)}")
            # If that fails, try the individual functions
            try:
                update_material_path(material_id, local_material_path, 'local')
                update_material_status(material_id, 'completed', 100)
                logger.info(f"✅ Fallback updates succeeded for material {material_id}")
            except Exception as fallback_e:
                logger.error(f"❌ All database updates failed: {str(fallback_e)}")
                # Last resort: just update status
                try:
                    update_material_status(material_id, 'completed', 100)
                    logger.info(f"✅ Status-only update succeeded for material {material_id}")
                except Exception as final_e:
                    logger.error(f"❌ Even status update failed: {str(final_e)}")
        
        # Clean up input file
        try:
            os.remove(input_file_path)
            logger.info(f"Cleaned up input file: {input_file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup input file {input_file_path}: {str(e)}")
        
        return local_material_path
        
    except Exception as e:
        logger.error(f"Error during HLS conversion: {str(e)}")
        logger.error(f"Conversion error traceback: {traceback.format_exc()}")
        
        # Update status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup temporary directory {temp_dir}: {str(cleanup_error)}")
        
        raise

def migrate_hls_to_b2(material_id: int, local_hls_path: str, video_id: str, category_code: str):
    """
    Process 2: Migrate HLS segments to B2 storage
    Status: archiving (0-100%)
    """
    logger.info(f"Starting B2 migration for material {material_id}")
    logger.info(f"Local HLS path: {local_hls_path}")
    
    try:
        # Get B2 storage service
        b2_storage_service = B2StorageService()
        
        # Update status to archiving
        update_material_status(material_id, 'archiving', 0)
        logger.info(f"Updated material {material_id} - Status: archiving, Progress: 0%")
        
        # Get local directory path
        local_dir = os.path.dirname(local_hls_path)
        
        # Create B2 directory structure
        current_date = datetime.now()
        b2_base_path = f"hls/{category_code}/{current_date.year}/{current_date.month:02d}/{video_id}"
        
        # Get all HLS files
        hls_files = [f for f in os.listdir(local_dir) if f.endswith(('.m3u8', '.ts'))]
        total_files = len(hls_files)
        
        if total_files == 0:
            raise Exception("No HLS files found to migrate")
        
        logger.info(f"Found {total_files} HLS files to migrate to B2")
        
        # Upload files to B2
        successful_uploads = 0
        
        for i, hls_file in enumerate(hls_files):
            local_file_path = os.path.join(local_dir, hls_file)
            b2_file_path = f"{b2_base_path}/{hls_file}"
            
            # Determine content type
            if hls_file.endswith('.m3u8'):
                content_type = 'application/vnd.apple.mpegurl'
            else:
                content_type = 'video/mp2t'
            
            try:
                # Upload file to B2
                b2_storage_service.upload_file(local_file_path, b2_file_path, content_type)
                
                successful_uploads += 1
                logger.info(f"Uploaded {hls_file} to B2 ({successful_uploads}/{total_files})")
                
                # Update progress
                progress = int((successful_uploads / total_files) * 100)
                update_material_status(material_id, 'archiving', progress)
                
            except Exception as e:
                logger.error(f"Failed to upload {hls_file} to B2: {str(e)}")
                raise
        
        # Update material path to B2
        b2_material_path = f"{b2_base_path}/output.m3u8"
        update_material_path(material_id, b2_material_path, 'b2')
        
        # Update status to completed
        update_material_status(material_id, 'completed', 100)
        logger.info(f"B2 migration completed successfully for material {material_id}")
        
        # Clean up local files
        try:
            shutil.rmtree(local_dir)
            logger.info(f"Cleaned up local HLS directory: {local_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup local directory {local_dir}: {str(e)}")
        
        return b2_material_path
        
    except Exception as e:
        logger.error(f"Error during B2 migration: {str(e)}")
        logger.error(f"Migration error traceback: {traceback.format_exc()}")
        
        # Update status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        raise

# Import celery instance
from celery_config import celery

# Register tasks with celery
@celery.task(bind=True, name='tasks.convert_video_to_hls', max_retries=3, default_retry_delay=60, soft_time_limit=3600, time_limit=3900)
def convert_video_to_hls_task(self, material_id: int, input_file_path: str, video_id: str, category_code: str):
    """
    Celery task wrapper for HLS conversion with enhanced logging
    """
    task_id = self.request.id
    logger.info(f"🎬 TASK STARTED - ID: {task_id} | Material: {material_id}")
    logger.info(f"📁 Input: {input_file_path}")
    logger.info(f"🆔 Video: {video_id} | Category: {category_code}")
    
    try:
        # Update task status in database
        update_material_status(material_id, 'processing', 0, f'Task started: {task_id}')
        logger.info(f"✅ Database updated - Material {material_id} set to processing")
        
        # Call the actual conversion function
        result = convert_video_to_hls(material_id, input_file_path, video_id, category_code)
        
        logger.info(f"🎉 TASK COMPLETED - ID: {task_id} | Material: {material_id}")
        return result
        
    except Exception as e:
        logger.error(f"💥 TASK FAILED - ID: {task_id} | Material: {material_id} | Error: {str(e)}")
        # Update database with error
        update_material_status(material_id, 'failed', 0, f'Task failed: {str(e)}')
        raise

@celery.task(bind=True, name='tasks.migrate_hls_to_b2', max_retries=3, default_retry_delay=60)
def migrate_hls_to_b2_task(self, material_id: int, local_hls_path: str, video_id: str, category_code: str):
    return migrate_hls_to_b2(material_id, local_hls_path, video_id, category_code)
