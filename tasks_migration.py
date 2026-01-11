import os
import logging
import traceback
from datetime import datetime
from config import UPLOAD_FOLDER
from celery import Celery
from storage.b2_storage_service import B2StorageService

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

def update_material_storage_location(material_id, storage_location, b2_path=None):
    """Update material storage location and optionally set b2_material_path (do not overwrite material_path)."""
    connection = None
    try:
        import pymysql
        
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            if b2_path:
                sql = """
                UPDATE subtopic_materials 
                SET storage_location = %s, b2_material_path = %s
                WHERE id = %s
                """
                cursor.execute(sql, (storage_location, b2_path, material_id))
            else:
                sql = """
                UPDATE subtopic_materials 
                SET storage_location = %s
                WHERE id = %s
                """
                cursor.execute(sql, (storage_location, material_id))
            
        logger.info(f"Updated material {material_id} storage location to: {storage_location}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating material storage location: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def update_material_status(material_id, status, progress=0, error_message=None):
    """Update material processing status and progress in database"""
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
        
    except Exception as e:
        logger.error(f"Error updating material status: {str(e)}")
        raise
    finally:
        if connection:
            connection.close()

def get_materials_for_migration():
    """Get materials that need to be migrated from local to B2"""
    connection = None
    try:
        import pymysql
        
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            sql = """
            SELECT id, name, material_path, storage_location
            FROM subtopic_materials 
            WHERE storage_location = 'local' 
            AND material_path != '' 
            AND processing_status = 'completed'
            AND extension_type = 'm3u8'
            """
            cursor.execute(sql)
            results = cursor.fetchall()
            
        return results
        
    except Exception as e:
        logger.error(f"Error getting materials for migration: {str(e)}")
        return []
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

def migrate_material_to_b2(material_id, local_path):
    """
    Migrate a material from local storage to B2
    """
    try:
        logger.info(f"Starting migration of material {material_id} from local to B2")
        logger.info(f"Local path: {local_path}")
        
        # Initialize B2 service
        b2_storage_service = B2StorageService()
        
        # local_path might be a directory path like "storage/uploads/hls/VIDEOS/YYYY/MM/UUID"
        # or a manifest file path like "storage/uploads/hls/VIDEOS/YYYY/MM/UUID/output.m3u8"
        # Build absolute manifest path and HLS directory using UPLOAD_FOLDER
        uploads_prefix = 'storage/uploads/'
        if local_path.startswith(uploads_prefix):
            rel_after_uploads = local_path[len(uploads_prefix):]
            manifest_local_abs = os.path.join(UPLOAD_FOLDER, rel_after_uploads)
        elif os.path.isabs(local_path):
            manifest_local_abs = local_path
        else:
            # Fallback: relative to current working directory
            manifest_local_abs = os.path.join(os.getcwd(), local_path)
        
        # Check if the path points to a directory (common case)
        if os.path.isdir(manifest_local_abs):
            # If it's a directory, look for output.m3u8 inside it
            manifest_file = os.path.join(manifest_local_abs, 'output.m3u8')
            if os.path.exists(manifest_file):
                manifest_local_abs = manifest_file
                hls_dir = os.path.dirname(manifest_local_abs)
            else:
                raise Exception(f"Manifest file not found in directory: {manifest_local_abs}")
        elif os.path.isfile(manifest_local_abs):
            # If it's already a file, use it directly
            hls_dir = os.path.dirname(manifest_local_abs)
        else:
            raise Exception(f"Manifest file not found: {manifest_local_abs}")
        
        # Derive B2 base path by stripping the leading "storage/uploads/" prefix
        rel_path = local_path
        uploads_prefix = 'storage/uploads/'
        if rel_path.startswith(uploads_prefix):
            rel_path = rel_path[len(uploads_prefix):]
        
        # If rel_path is a directory, use it directly; if it's a file, get its directory
        if rel_path.endswith('.m3u8'):
            rel_dir = os.path.dirname(rel_path)  # "hls/VIDEOS/YYYY/MM/UUID"
        else:
            rel_dir = rel_path  # "hls/VIDEOS/YYYY/MM/UUID"
        
        # Create B2 directory structure (use the same relative directory)
        b2_base_path = rel_dir
        
        logger.info(f"B2 base path: {b2_base_path}")
        
        # Upload manifest first
        manifest_b2_path = f"{b2_base_path}/output.m3u8"
        
        logger.info(f"Uploading manifest: {manifest_b2_path}")
        with open(manifest_local_abs, 'rb') as f:
            manifest_data = f.read()
        
        b2_storage_service.upload_file_data(
            manifest_data, 
            manifest_b2_path, 
            'application/vnd.apple.mpegurl'
        )
        logger.info(f"✅ Manifest uploaded successfully")
        
        # Upload segments
        segment_files = [f for f in os.listdir(hls_dir) if f.endswith('.ts')]
        segment_files.sort()
        
        total_segments = len(segment_files)
        logger.info(f"Found {total_segments} segment files to upload")
        
        successful_uploads = 0
        failed_uploads = 0
        
        for i, segment_file in enumerate(segment_files):
            segment_local = os.path.join(hls_dir, segment_file)
            segment_b2_path = f"{b2_base_path}/{segment_file}"
            
            try:
                with open(segment_local, 'rb') as f:
                    segment_data = f.read()
                
                b2_storage_service.upload_file_data(
                    segment_data, 
                    segment_b2_path, 
                    'video/MP2T'
                )
                
                successful_uploads += 1
                
                # Log progress every 10 segments
                if (i + 1) % 10 == 0 or (i + 1) == total_segments:
                    progress = ((i + 1) / total_segments) * 100
                    logger.info(f"Migration progress: {progress:.1f}% ({i + 1}/{total_segments})")
                    
                    # Update database progress for migration
                    update_material_status(material_id, 'processing', int(progress))
                    
            except Exception as e:
                failed_uploads += 1
                logger.error(f"Failed to upload {segment_file}: {str(e)}")
        
        # Check upload results
        if failed_uploads > 0:
            error_msg = f"Migration completed with {failed_uploads} failures out of {total_segments} segments"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        logger.info(f"Successfully uploaded all {total_segments} segments to B2")
        
        # Update database to reflect B2 storage
        update_material_storage_location(material_id, 'b2', manifest_b2_path)
        
        # Clean up local files
        try:
            import shutil
            shutil.rmtree(hls_dir)
            logger.info(f"Cleaned up local directory: {hls_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup local directory {local_full_path}: {str(e)}")
        
        logger.info(f"Migration completed successfully for material {material_id}")
        return manifest_b2_path
        
    except Exception as e:
        logger.error(f"Error in migrate_material_to_b2: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

@celery.task(bind=True, name='tasks.migrate_to_b2', max_retries=3, default_retry_delay=60)
def migrate_to_b2(self, material_id: int):
    """
    Migrate a material from local storage to B2
    
    Args:
        material_id: Database material ID
    """
    logger.info(f"Starting B2 migration for material {material_id}")
    
    try:
        # Get material details
        connection = None
        try:
            import pymysql
            
            connection = pymysql.connect(**DB_CONFIG)
            
            with connection.cursor() as cursor:
                sql = """
                SELECT material_path, storage_location, extension_type
                FROM subtopic_materials 
                WHERE id = %s
                """
                cursor.execute(sql, (material_id,))
                result = cursor.fetchone()
                
            if not result:
                raise Exception(f"Material {material_id} not found")
                
            local_path, storage_location, extension_type = result
            
            # Skip documents (PDFs) - they don't need B2 migration
            if extension_type == 'pdf':
                logger.info(f"Skipping material {material_id} - it's a document (PDF), not a video")
                return None
            
            if storage_location != 'local':
                raise Exception(f"Material {material_id} is not in local storage (current: {storage_location})")
                
            if not local_path:
                raise Exception(f"Material {material_id} has no local path")
                
        except Exception as e:
            logger.error(f"Error getting material details: {str(e)}")
            raise
        finally:
            if connection:
                connection.close()
        
        # Migrate to B2
        b2_path = migrate_material_to_b2(material_id, local_path)
        
        logger.info(f"B2 migration completed successfully for material {material_id}")
        return b2_path
        
    except Exception as e:
        logger.error(f"Error during B2 migration: {str(e)}")
        logger.error(f"Migration error traceback: {traceback.format_exc()}")
        raise

@celery.task(bind=True, name='tasks.migrate_all_to_b2', max_retries=3, default_retry_delay=60)
def migrate_all_to_b2(self):
    """
    Migrate all local materials to B2 storage
    """
    logger.info("Starting migration of all local materials to B2")
    
    try:
        # Get materials for migration
        materials = get_materials_for_migration()
        
        if not materials:
            logger.info("No materials found for migration")
            return []
        
        logger.info(f"Found {len(materials)} materials to migrate")
        
        successful_migrations = []
        failed_migrations = []
        total_materials = len(materials)
        
        for i, (material_id, name, local_path, storage_location) in enumerate(materials):
            try:
                logger.info(f"Migrating material {material_id} ({name}) - {i+1}/{total_materials}")
                
                # Update overall migration progress
                overall_progress = int(((i + 1) / total_materials) * 100)
                logger.info(f"Bulk migration progress: {overall_progress}% ({i+1}/{total_materials})")
                
                b2_path = migrate_material_to_b2(material_id, local_path)
                successful_migrations.append((material_id, b2_path))
                logger.info(f"✅ Successfully migrated material {material_id}")
                
            except Exception as e:
                failed_migrations.append((material_id, str(e)))
                logger.error(f"❌ Failed to migrate material {material_id}: {str(e)}")
        
        # Summary
        logger.info(f"Migration completed:")
        logger.info(f"✅ Successful: {len(successful_migrations)}")
        logger.info(f"❌ Failed: {len(failed_migrations)}")
        
        if failed_migrations:
            logger.error("Failed migrations:")
            for material_id, error in failed_migrations:
                logger.error(f"  Material {material_id}: {error}")
        
        return {
            'successful': successful_migrations,
            'failed': failed_migrations
        }
        
    except Exception as e:
        logger.error(f"Error during bulk migration: {str(e)}")
        logger.error(f"Bulk migration error traceback: {traceback.format_exc()}")
        raise
