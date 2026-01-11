from celery_config import celery
from database.db_connector import DBConnector
from sqlalchemy.orm import Session
from studies.models.models import SubtopicMaterial, StudyMaterialCategory
import logging
import subprocess
import os
import shutil
import json
import traceback
import re
from sqlalchemy import text
from datetime import datetime
import uuid
import redis
import pymysql
from celery import current_task
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# Debug: Log database configuration (without password)
logger.info(f"Database config - Host: {DB_CONFIG['host']}, User: {DB_CONFIG['user']}, Database: {DB_CONFIG['database']}")

def get_db_connection():
    """Get a direct MySQL connection"""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        if connection:
            connection.close()
        raise

def update_material_status(material_id, status, progress=0, error=None):
    """Update material status using direct MySQL"""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            if error:
                sql = """
                UPDATE subtopic_materials 
                SET processing_status = %s, processing_progress = %s, processing_error = %s, updated_at = NOW()
                WHERE id = %s
                """
                cursor.execute(sql, (status, progress, error, material_id))
            else:
                sql = """
                UPDATE subtopic_materials 
                SET processing_status = %s, processing_progress = %s, processing_error = NULL, updated_at = NOW()
                WHERE id = %s
                """
                cursor.execute(sql, (status, progress, material_id))
            
            connection.commit()
            logger.info(f"Updated material {material_id} - Progress: {progress}%, Status: {status}, Error: {error}")
            return True
    except Exception as e:
        logger.error(f"Error updating material status: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def get_material_info(material_id, max_retries=3, delay_seconds=2):
    """Get material information using direct MySQL with retry mechanism"""
    connection = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"=== DEBUG: Attempt {attempt + 1}/{max_retries} - Starting get_material_info for material {material_id} ===")
            logger.info(f"=== DEBUG: DB_CONFIG = {DB_CONFIG} ===")
            
            connection = get_db_connection()
            logger.info(f"=== DEBUG: Database connection successful ===")
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                SELECT id, subtopic_id, material_category_id, name, material_path, 
                       extension_type, processing_status, processing_progress, processing_error
                FROM subtopic_materials 
                WHERE id = %s
                """
                logger.info(f"=== DEBUG: Executing SQL: {sql} with material_id = {material_id} ===")
                cursor.execute(sql, (material_id,))
                material = cursor.fetchone()
                
                logger.info(f"=== DEBUG: Looking for material {material_id} ===")
                if material:
                    logger.info(f"=== DEBUG: Found material: {material} ===")
                    # Get category information
                    sql = """
                    SELECT code, name 
                    FROM study_material_categories 
                    WHERE id = %s
                    """
                    cursor.execute(sql, (material['material_category_id'],))
                    category = cursor.fetchone()
                    material['category'] = category
                    logger.info(f"=== DEBUG: Category info: {category} ===")
                    return material
                else:
                    logger.warning(f"=== DEBUG: Material {material_id} not found on attempt {attempt + 1} ===")
                    # Let's check what materials exist
                    cursor.execute("SELECT id, name FROM subtopic_materials ORDER BY id DESC LIMIT 5")
                    recent_materials = cursor.fetchall()
                    logger.info(f"=== DEBUG: Recent materials: {recent_materials} ===")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"=== DEBUG: Waiting {delay_seconds} seconds before retry ===")
                        import time
                        time.sleep(delay_seconds)
                        continue
                    else:
                        logger.error(f"=== DEBUG: Material {material_id} not found after {max_retries} attempts ===")
                        return None
            
        except Exception as e:
            logger.error(f"=== DEBUG: Error getting material info (attempt {attempt + 1}): {str(e)} ===")
            if attempt < max_retries - 1:
                logger.info(f"=== DEBUG: Waiting {delay_seconds} seconds before retry ===")
                import time
                time.sleep(delay_seconds)
                continue
            else:
                logger.error(f"=== DEBUG: Error traceback: {traceback.format_exc()} ===")
                return None
        finally:
            if connection:
                connection.close()
                logger.info(f"=== DEBUG: Database connection closed ===")
    
    return None

def update_material_path(material_id, new_path):
    """Update material path using direct MySQL"""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
            UPDATE subtopic_materials 
            SET material_path = %s, updated_at = NOW()
            WHERE id = %s
            """
            cursor.execute(sql, (new_path, material_id))
            connection.commit()
            logger.info(f"Updated material {material_id} path to: {new_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating material path: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def convert_to_hls(material_id, input_path, output_dir, task_id):
    try:
        logger.info(f"Starting HLS conversion for material_id={material_id}, task_id={task_id}")
        logger.info(f"Input path: {input_path}")
        logger.info(f"Output directory: {output_dir}")
        
        # HLS output path
        hls_output_path = os.path.join(output_dir, "output.m3u8")
        
        # Set up FFmpeg path and environment
        # macOS path (dev)
        # ffmpeg_path = '/usr/local/bin/ffmpeg'
        # Linux path (production)
        ffmpeg_path = '/usr/bin/ffmpeg'
        
        if not os.path.exists(ffmpeg_path):
            logger.error(f"FFmpeg not found at {ffmpeg_path}")
            raise RuntimeError(f"FFmpeg not found at {ffmpeg_path}. Please ensure FFmpeg is installed.")

        # Create a new environment with the system PATH
        # macOS PATH
        env = os.environ.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
        # Linux PATH
        # env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin'

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
                env=env,
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

        # Construct FFmpeg command with progress reporting
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
            '-hls_segment_filename', f'{output_dir}/segment_%03d.ts',
            '-f', 'hls',
            '-progress', 'pipe:1',  # Output progress to stdout
            hls_output_path
        ]

        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Environment PATH: {env['PATH']}")

        # Start FFmpeg process with timeout handling
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
                    if time_str != 'N/A':
                        time_ms = int(time_str)
                        progress = min(int((time_ms / total_duration_ms) * 100), 100)
                        
                        # Only update if progress has changed
                        if progress > last_progress:
                            last_progress = progress
                            logger.info(f"Progress update: {progress}%")
                            
                            # Update Redis progress
                            redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
                            redis_client.set(f"task_progress:{task_id}", progress)
                            logger.info(f"Updating Redis progress for task {task_id}: {progress}%")
                            
                            # Update database progress
                            status = 'completed' if progress == 100 else 'processing'
                            if update_material_status(material_id, status, progress):
                                logger.info(f"Successfully updated progress for material {material_id}")
                            else:
                                logger.error(f"Failed to update progress for material {material_id}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing progress: {str(e)}")
                    logger.error(f"Problematic line: {line}")
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
            
        # Final progress update to ensure 100% is set
        if last_progress < 100:
            logger.info("Setting final progress to 100%")
            redis_client.set(f"task_progress:{task_id}", 100)
            update_material_status(material_id, 'completed')
            
        # Return the relative path for the database
        relative_path = os.path.join('hls', 'VIDEOS', 
                                   datetime.now().strftime('%Y'), 
                                   datetime.now().strftime('%m'),
                                   os.path.basename(output_dir),
                                   "output.m3u8")
        return relative_path
        
    except Exception as e:
        logger.error(f"Error in convert_to_hls: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Update material status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        raise

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

def process_document(material_id: int, file_path: str, output_dir: str, category_code: str):
    """Process document files (PDF, DOC, etc.)"""
    try:
        logger.info(f"Processing document for material {material_id}")
        
        # For documents, we'll just copy them to the output directory
        # and create a simple metadata file
        file_name = os.path.basename(file_path)
        output_path = os.path.join(output_dir, file_name)
        
        # Copy the document
        shutil.copy2(file_path, output_path)
        
        # Create metadata file
        metadata = {
            'original_name': file_name,
            'file_type': 'document',
            'processed_at': datetime.now().isoformat(),
            'file_size': os.path.getsize(file_path)
        }
        
        metadata_path = os.path.join(output_dir, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Return the relative path for the database
        relative_path = os.path.join('materials', 
                                   category_code,
                                   datetime.now().strftime('%Y'), 
                                   datetime.now().strftime('%m'),
                                   os.path.basename(output_dir),
                                   file_name)
        
        return relative_path
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        logger.error(f"Document processing error traceback: {traceback.format_exc()}")
        # Update status to failed if there's an error
        update_material_status(material_id, 'failed', 0, str(e))
        raise

@celery.task(bind=True, name='tasks.process_video', max_retries=3, default_retry_delay=60)
def process_video(self, material_id: int, file_path: str):
    """Process video file and convert to HLS format, or handle documents"""
    logger.info(f"Starting processing for material {material_id}")
    logger.info(f"File path: {file_path}")
    
    redis_client = None
    
    try:
        # Get material information using direct MySQL
        material = get_material_info(material_id)
        if not material:
            raise RuntimeError(f"Material {material_id} not found in database")
        
        # Check if material is already completed
        if material['processing_status'] == 'completed':
            logger.info(f"Material {material_id} is already completed, skipping processing")
            return material['material_path']
            
        # Check file size
        file_size_mb = get_file_size_mb(file_path)
        if file_size_mb > 1200:
            error_msg = f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size of 1200MB"
            logger.error(error_msg)
            update_material_status(material_id, 'failed', 0, error_msg)
            raise ValueError(error_msg)
            
        # Update status to processing
        update_material_status(material_id, 'processing', 0)
        logger.info(f"Updated material {material_id} - Progress: 0%, Status: processing, Error: None")

        # Get category information
        if not material.get('category'):
            raise RuntimeError(f"Material category not found for material {material_id}")
        
        category = material['category']
        
        # Determine file type
        file_type = get_file_type(file_path)
        logger.info(f"Processing {file_type} of size: {file_size_mb:.2f}MB")
            
        # Extract the UUID from the material_path
        path_parts = material['material_path'].split('/')
        if len(path_parts) < 5:
            raise RuntimeError(f"Invalid material path format: {material['material_path']}")
        
        # Get the UUID from the path
        file_id = path_parts[-2]  # UUID is the second-to-last part
            
        if file_type == 'video':
            # Create output directory for video
            output_dir = os.path.join('hls', 'VIDEOS', 
                                    datetime.now().strftime('%Y'), 
                                    datetime.now().strftime('%m'),
                                    file_id)
            full_output_dir = os.path.join('storage', 'uploads', output_dir)
            os.makedirs(full_output_dir, exist_ok=True)
            logger.info(f"Video output directory: {full_output_dir}")

            # Initialize Redis client for video progress
            redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

            # Convert video to HLS format
            try:
                relative_path = convert_to_hls(material_id, file_path, full_output_dir, self.request.id)
                logger.info(f"Video converted successfully. HLS path: {relative_path}")
                
                # Update material path and status
                update_material_path(material_id, relative_path)
                update_material_status(material_id, 'completed', 100)
                logger.info(f"Updated material path and status in database: {relative_path}")
                    
                return relative_path
                
            except Exception as e:
                logger.error(f"Error during video conversion: {str(e)}")
                logger.error(f"Conversion error traceback: {traceback.format_exc()}")
                # Update status to failed
                update_material_status(material_id, 'failed', 0, str(e))
                raise
                
        elif file_type == 'document':
            # Create output directory for document using category code
            output_dir = os.path.join('materials', 
                                    category['code'],
                                    datetime.now().strftime('%Y'), 
                                    datetime.now().strftime('%m'),
                                    file_id)
            full_output_dir = os.path.join('storage', 'uploads', output_dir)
            os.makedirs(full_output_dir, exist_ok=True)
            logger.info(f"Document output directory: {full_output_dir}")
            
            # Process document
            try:
                relative_path = process_document(material_id, file_path, full_output_dir, category['code'])
                logger.info(f"Document processed successfully. Path: {relative_path}")
                
                # Update material path and status
                update_material_path(material_id, relative_path)
                update_material_status(material_id, 'completed', 100)
                logger.info(f"Updated material path and status in database: {relative_path}")
                
                return relative_path
                
            except Exception as e:
                logger.error(f"Error during document processing: {str(e)}")
                logger.error(f"Document processing error traceback: {traceback.format_exc()}")
                # Update status to failed
                update_material_status(material_id, 'failed', 0, str(e))
                raise
        else:
            error_msg = f"Unsupported file type: {file_type}"
            logger.error(error_msg)
            # Update status to failed
            update_material_status(material_id, 'failed', 0, error_msg)
            raise ValueError(error_msg)
            
    except Exception as e:
        logger.error(f"Error in process_video: {str(e)}")
        logger.error(f"Process error traceback: {traceback.format_exc()}")
        # Update status to failed
        update_material_status(material_id, 'failed', 0, str(e))
        raise
        
    finally:
        # Cleanup resources
        if redis_client:
            try:
                # Remove progress key from Redis
                redis_client.delete(f"task_progress:{self.request.id}")
            except Exception as e:
                logger.error(f"Error cleaning up Redis: {str(e)}")
        
        # Force garbage collection
        import gc
        gc.collect()
        
        logger.info(f"Completed processing for material {material_id}")

def get_queue_status():
    """Get the current status of the video processing queue"""
    try:
        redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
        
        # Get queue length
        queue_length = redis_client.llen('celery')
        
        # Get active tasks
        active_tasks = []
        for key in redis_client.keys('celery-task-meta-*'):
            task_data = redis_client.get(key)
            if task_data:
                try:
                    task_info = json.loads(task_data)
                    if task_info.get('status') == 'STARTED':
                        active_tasks.append({
                            'task_id': task_info.get('task_id'),
                            'started_at': task_info.get('date_done'),
                            'material_id': task_info.get('args', [])[0] if task_info.get('args') else None
                        })
                except json.JSONDecodeError:
                    continue
        
        # Get task progress
        task_progress = {}
        for key in redis_client.keys('task_progress:*'):
            task_id = key.decode('utf-8').split(':')[1]
            progress = redis_client.get(key)
            if progress:
                task_progress[task_id] = int(progress)
        
        return {
            'queue_length': queue_length,
            'active_tasks': active_tasks,
            'task_progress': task_progress
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        return {
            'error': str(e),
            'queue_length': 0,
            'active_tasks': [],
            'task_progress': {}
        } 