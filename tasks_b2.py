import os
import logging
import subprocess
import re
import traceback
import tempfile
import shutil
from datetime import datetime
from celery import Celery
from storage.b2_storage_service import B2StorageService
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Celery instance
from celery_config import celery

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

def convert_time_to_seconds(time_str):
    """Convert HH:MM:SS format to seconds"""
    if not time_str or ':' not in time_str:
        return None
    
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        else:
            return int(time_str)
    except (ValueError, TypeError):
        return None

def get_file_size_mb(file_path):
    """Get file size in megabytes"""
    try:
        return os.path.getsize(file_path) / (1024 * 1024)
    except Exception as e:
        logger.error(f"Error getting file size: {str(e)}")
        return 0

def get_file_type(file_path):
    """Determine if the file is a video or document based on extension"""
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'}
    document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
    
    _, ext = os.path.splitext(file_path.lower())
    if ext in video_extensions:
        return 'video'
    elif ext in document_extensions:
        return 'document'
    else:
        return 'unknown'

def update_material_status(material_id, status, progress=0, error_message=None):
    """Update material processing status in database using direct MySQL"""
    connection = None
    try:
        import pymysql
        
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            sql = """
            UPDATE subtopic_materials 
            SET processing_status = %s, processing_progress = %s, processing_error = %s
            WHERE id = %s
            """
            cursor.execute(sql, (status, progress, error_message, material_id))
            
        logger.info(f"Updated material {material_id} - Status: {status}, Progress: {progress}%")
        return True
        
    except Exception as e:
        logger.error(f"Error updating material status: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def update_material_path(material_id, new_path):
    """Update material path in database using direct MySQL"""
    connection = None
    try:
        import pymysql
        
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            sql = """
            UPDATE subtopic_materials 
            SET material_path = %s
            WHERE id = %s
            """
            cursor.execute(sql, (new_path, material_id))
            
        logger.info(f"Updated material {material_id} path to: {new_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating material path: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def upload_file_to_b2(b2_storage_service, local_path, b2_path, content_type, file_index, total_files):
    """Upload a single file to B2 with progress tracking"""
    try:
        with open(local_path, 'rb') as f:
            file_data = f.read()
        
        b2_storage_service.upload_file_data(file_data, b2_path, content_type)
        logger.info(f"Uploaded file {file_index + 1}/{total_files} to B2: {b2_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload {b2_path}: {str(e)}")
        return False

def convert_to_hls_b2(material_id: int, input_path: str, video_id: str, category_code: str):
    """
    Convert video to HLS format and upload to B2 with optimized parallel uploads
    """
    temp_dir = None
    b2_storage_service = B2StorageService()
    
    try:
        logger.info(f"Starting B2 HLS conversion for material_id={material_id}")
        logger.info(f"Input path: {input_path}")
        
        # Create temporary directory for HLS processing
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # HLS output path in temp directory
        hls_output_path = os.path.join(temp_dir, "output.m3u8")
        
        # Set up FFmpeg path - macOS path
        ffmpeg_path = '/usr/local/bin/ffmpeg'
        
        if not os.path.exists(ffmpeg_path):
            logger.error(f"FFmpeg not found at {ffmpeg_path}")
            raise RuntimeError(f"FFmpeg not found at {ffmpeg_path}. Please ensure FFmpeg is installed.")

        # Get video duration first
        try:
            duration_cmd = [
                ffmpeg_path,
                '-i', input_path,
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
            '-i', input_path,
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
            '-hls_segment_filename', f'{temp_dir}/segment_%03d.ts',
            '-f', 'hls',
            '-progress', 'pipe:1',  # Output progress to stdout
            hls_output_path
        ]

        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")

        # Start FFmpeg process with timeout handling
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        last_progress = 0
        # Monitor progress (conversion phase - 0-70% of total progress)
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
                        
                        # Convert conversion progress to overall progress (0-70%)
                        overall_progress = int((conversion_progress * 70) / 100)
                        
                        # Only update if progress has changed significantly (every 5%)
                        if overall_progress > last_progress and (overall_progress - last_progress) >= 5:
                            last_progress = overall_progress
                            logger.info(f"Conversion progress: {conversion_progress}% (Overall: {overall_progress}%)")
                            
                            # Update database progress
                            status = 'processing'
                            update_material_status(material_id, status, overall_progress)
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
        if not os.path.exists(hls_output_path):
            raise Exception("HLS manifest file was not created")
        
        # Upload HLS files to B2 with parallel processing
        logger.info("Starting parallel upload of HLS files to B2...")
        
        # Create B2 directory structure
        current_date = datetime.now()
        b2_base_path = f"hls/{category_code}/{current_date.year}/{current_date.month:02d}/{video_id}"
        
        # Prepare upload tasks
        upload_tasks = []
        
        # Add manifest file
        manifest_b2_path = f"{b2_base_path}/output.m3u8"
        upload_tasks.append({
            'local_path': hls_output_path,
            'b2_path': manifest_b2_path,
            'content_type': 'application/vnd.apple.mpegurl',
            'file_index': 0,
            'is_manifest': True
        })
        
        # Add segment files
        segment_files = [f for f in os.listdir(temp_dir) if f.endswith('.ts')]
        segment_files.sort()  # Ensure proper order
        
        for i, segment_file in enumerate(segment_files):
            segment_path = os.path.join(temp_dir, segment_file)
            segment_b2_path = f"{b2_base_path}/{segment_file}"
            upload_tasks.append({
                'local_path': segment_path,
                'b2_path': segment_b2_path,
                'content_type': 'video/MP2T',
                'file_index': i + 1,
                'is_manifest': False
            })
        
        total_files = len(upload_tasks)
        logger.info(f"Prepared {total_files} files for upload (1 manifest + {len(segment_files)} segments)")
        
        # Upload files in parallel with progress tracking
        max_workers = min(10, total_files)  # Limit concurrent uploads
        successful_uploads = 0
        failed_uploads = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all upload tasks
            future_to_task = {}
            for task in upload_tasks:
                future = executor.submit(
                    upload_file_to_b2,
                    b2_storage_service,
                    task['local_path'],
                    task['b2_path'],
                    task['content_type'],
                    task['file_index'],
                    total_files
                )
                future_to_task[future] = task
            
            # Process completed uploads
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    if success:
                        successful_uploads += 1
                        # Update progress every 10 files or for manifest
                        if task['is_manifest'] or successful_uploads % 10 == 0:
                            upload_progress = int((successful_uploads / total_files) * 100)
                            # Convert upload progress to overall progress (70-100%)
                            overall_progress = 70 + int((upload_progress * 30) / 100)
                            logger.info(f"Upload progress: {upload_progress}% ({successful_uploads}/{total_files} files) - Overall: {overall_progress}%")
                            
                            # Update database progress
                            update_material_status(material_id, 'processing', overall_progress)
                    else:
                        failed_uploads += 1
                        logger.error(f"Failed to upload: {task['b2_path']}")
                except Exception as e:
                    failed_uploads += 1
                    logger.error(f"Exception during upload of {task['b2_path']}: {str(e)}")
        
        # Check upload results
        if failed_uploads > 0:
            error_msg = f"Upload completed with {failed_uploads} failures out of {total_files} files"
            logger.error(error_msg)
            update_material_status(material_id, 'failed', 0, error_msg)
            raise Exception(error_msg)
        
        logger.info(f"Successfully uploaded all {total_files} files to B2")
        
        # Final progress update
        update_material_status(material_id, 'completed', 100)
        
        logger.info(f"B2 HLS conversion completed successfully")
        return manifest_b2_path
        
    except Exception as e:
        logger.error(f"Error in convert_to_hls_b2: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Update material status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        raise
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Failed to cleanup temporary directory {temp_dir}: {str(e)}")

@celery.task(bind=True, name='tasks.process_video_b2', max_retries=3, default_retry_delay=60)
def process_video_b2(self, material_id: int, temp_file_path: str, video_id: str, category_code: str):
    """
    Process video file and convert to HLS format, then upload to B2
    
    Args:
        material_id: Database material ID
        temp_file_path: Path to temporary video file
        video_id: Unique video identifier
        category_code: Material category code
    """
    logger.info(f"Starting B2 video processing for material {material_id}")
    logger.info(f"Temp file path: {temp_file_path}")
    
    try:
        # Get B2 storage service
        b2_storage_service = B2StorageService()
        
        # Check file size
        file_size_mb = get_file_size_mb(temp_file_path)
        if file_size_mb > 1200:
            error_msg = f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size of 1200MB"
            logger.error(error_msg)
            update_material_status(material_id, 'failed', 0, error_msg)
            raise ValueError(error_msg)
        
        # Update status to processing
        update_material_status(material_id, 'processing', 0)
        logger.info(f"Updated material {material_id} - Progress: 0%, Status: processing")
        
        # Determine file type
        file_type = get_file_type(temp_file_path)
        logger.info(f"Processing {file_type} of size: {file_size_mb:.2f}MB")
        
        if file_type == 'video':
            # Convert video to HLS and upload to B2
            try:
                b2_manifest_path = convert_to_hls_b2(
                    material_id, 
                    temp_file_path, 
                    video_id, 
                    category_code
                )
                
                # Update material path to B2 path
                update_material_path(material_id, b2_manifest_path)
                logger.info(f"Updated material path to B2: {b2_manifest_path}")
                
                return b2_manifest_path
                
            except Exception as e:
                logger.error(f"Error during B2 video conversion: {str(e)}")
                logger.error(f"Conversion error traceback: {traceback.format_exc()}")
                # Update status to failed
                update_material_status(material_id, 'failed', 0, str(e))
                raise
        else:
            error_msg = f"Unsupported file type: {file_type}"
            logger.error(error_msg)
            update_material_status(material_id, 'failed', 0, error_msg)
            raise ValueError(error_msg)
            
    except Exception as e:
        logger.error(f"Error in process_video_b2: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Update status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        raise
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup temporary file {temp_file_path}: {str(e)}")
