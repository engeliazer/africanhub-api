import os
import logging
import subprocess
import re
import traceback
import tempfile
import shutil
from datetime import datetime
from celery import Celery

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

def get_file_size_mb(file_path):
    """Get file size in megabytes"""
    try:
        return os.path.getsize(file_path) / (1024 * 1024)
    except Exception as e:
        logger.error(f"Error getting file size: {str(e)}")
        return 0

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

def update_material_path(material_id, new_path, storage_location='local'):
    """Update material path and storage location in database using direct MySQL"""
    connection = None
    try:
        import pymysql
        
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            sql = """
            UPDATE subtopic_materials 
            SET material_path = %s, storage_location = %s
            WHERE id = %s
            """
            cursor.execute(sql, (new_path, storage_location, material_id))
            
        logger.info(f"Updated material {material_id} path to: {new_path} (storage: {storage_location})")
        return True
        
    except Exception as e:
        logger.error(f"Error updating material path: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def convert_to_hls_local(material_id: int, input_path: str, video_id: str, category_code: str):
    """
    Convert video to HLS format and save to local storage
    """
    temp_dir = None
    
    try:
        logger.info(f"Starting local HLS conversion for material_id={material_id}")
        logger.info(f"Input path: {input_path}")
        
        # Create local HLS directory structure
        current_date = datetime.now()
        local_base_path = f"storage/uploads/hls/{category_code}/{current_date.year}/{current_date.month:02d}/{video_id}"
        local_full_path = os.path.join(os.getcwd(), local_base_path)
        
        # Ensure directory exists
        os.makedirs(local_full_path, exist_ok=True)
        logger.info(f"Created local directory: {local_full_path}")
        
        # HLS output path in local directory
        hls_output_path = os.path.join(local_full_path, "output.m3u8")
        
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
            '-hls_segment_filename', f'{local_full_path}/segment_%03d.ts',
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
        # Monitor progress
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if 'out_time_ms=' in line:
                try:
                    time_str = line.split('=')[1].strip()
                    if time_str != 'N/A' and total_duration_ms > 0:
                        time_ms = int(time_str)
                        progress = min(int((time_ms / total_duration_ms) * 100), 100)
                        
                        # Only update if progress has changed
                        if progress > last_progress:
                            last_progress = progress
                            logger.info(f"Progress update: {progress}%")
                            
                            # Update database progress
                            status = 'completed' if progress == 100 else 'processing'
                            update_material_status(material_id, status, progress)
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
        
        # Count segments
        segment_files = [f for f in os.listdir(local_full_path) if f.endswith('.ts')]
        logger.info(f"Successfully created {len(segment_files)} segments locally")
        
        # Final progress update
        update_material_status(material_id, 'completed', 100)
        
        logger.info(f"Local HLS conversion completed successfully")
        return local_base_path
        
    except Exception as e:
        logger.error(f"Error in convert_to_hls_local: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Update material status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        raise

@celery.task(bind=True, name='tasks.process_video_local', max_retries=3, default_retry_delay=60)
def process_video_local(self, material_id: int, temp_file_path: str, video_id: str, category_code: str):
    """
    Process video file and convert to HLS format, then save to local storage
    
    Args:
        material_id: Database material ID
        temp_file_path: Path to temporary video file
        video_id: Unique video identifier
        category_code: Material category code
    """
    logger.info(f"Starting local video processing for material {material_id}")
    logger.info(f"Temp file path: {temp_file_path}")
    
    try:
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
        
        # Process video of size
        logger.info(f"Processing video of size: {file_size_mb:.2f}MB")
        
        # Convert to HLS and save locally
        local_path = convert_to_hls_local(
            material_id,
            temp_file_path,
            video_id,
            category_code
        )
        
        # Update material path to local storage
        update_material_path(material_id, local_path, 'local')
        logger.info(f"Updated material path to local: {local_path}")
        
        # Clean up temporary file
        try:
            os.remove(temp_file_path)
            logger.info(f"Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup temporary file {temp_file_path}: {str(e)}")
        
        logger.info(f"Local video processing completed successfully for material {material_id}")
        return local_path
        
    except Exception as e:
        logger.error(f"Error during local video conversion: {str(e)}")
        logger.error(f"Conversion error traceback: {traceback.format_exc()}")
        # Update material status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        logger.error(f"Error in process_video_local: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
