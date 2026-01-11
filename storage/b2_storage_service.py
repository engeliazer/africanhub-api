import os
import logging
from typing import Optional, Dict, Any
from b2sdk.v2 import *
from datetime import datetime
import tempfile
import shutil

logger = logging.getLogger(__name__)

class B2StorageService:
    def __init__(self):
        self.api = None
        self.bucket = None
        self.bucket_name = os.getenv('B2_BUCKET_NAME')
        self.application_key_id = os.getenv('B2_APPLICATION_KEY_ID')
        self.application_key = os.getenv('B2_APPLICATION_KEY')
        
        if not all([self.bucket_name, self.application_key_id, self.application_key]):
            raise ValueError("B2 credentials not properly configured. Please set B2_BUCKET_NAME, B2_APPLICATION_KEY_ID, and B2_APPLICATION_KEY environment variables.")
        
        self._initialize_b2()
    
    def _initialize_b2(self):
        """Initialize B2 API and get bucket reference"""
        try:
            # Create B2 API instance
            self.api = B2Api()
            
            # Authenticate with B2
            self.api.authorize_account("production", self.application_key_id, self.application_key)
            logger.info("Successfully authenticated with B2")
            
            # Get bucket reference
            self.bucket = self.api.get_bucket_by_name(self.bucket_name)
            logger.info(f"Successfully connected to B2 bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize B2: {str(e)}")
            raise
    
    def upload_file(self, local_file_path: str, b2_file_path: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a file to B2
        
        Args:
            local_file_path: Path to local file
            b2_file_path: Desired path in B2 bucket
            content_type: MIME type of the file
            
        Returns:
            Dict containing file info (file_id, file_name, content_length, content_sha1, etc.)
        """
        try:
            # Determine content type if not provided
            if not content_type:
                content_type = self._get_content_type(local_file_path)
            
            # Upload file to B2
            uploaded_file = self.bucket.upload_local_file(
                local_file=local_file_path,
                file_name=b2_file_path,
                content_type=content_type
            )
            
            logger.info(f"Successfully uploaded {local_file_path} to B2 as {b2_file_path}")
            
            return {
                'file_id': uploaded_file.id_,
                'file_name': uploaded_file.file_name,
                'content_length': uploaded_file.size,
                'content_sha1': uploaded_file.content_sha1,
                'content_type': uploaded_file.content_type,
                'upload_timestamp': uploaded_file.upload_timestamp,
                'b2_file_path': b2_file_path
            }
            
        except Exception as e:
            logger.error(f"Failed to upload {local_file_path} to B2: {str(e)}")
            raise
    
    def upload_file_data(self, file_data: bytes, b2_file_path: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload file data directly to B2
        
        Args:
            file_data: File data as bytes
            b2_file_path: Desired path in B2 bucket
            content_type: MIME type of the file
            
        Returns:
            Dict containing file info
        """
        try:
            # Determine content type if not provided
            if not content_type:
                content_type = self._get_content_type_from_path(b2_file_path)
            
            # Upload file data to B2
            uploaded_file = self.bucket.upload_bytes(
                data_bytes=file_data,
                file_name=b2_file_path,
                content_type=content_type
            )
            
            logger.info(f"Successfully uploaded data to B2 as {b2_file_path}")
            
            return {
                'file_id': uploaded_file.id_,
                'file_name': uploaded_file.file_name,
                'content_length': uploaded_file.size,
                'content_sha1': uploaded_file.content_sha1,
                'content_type': uploaded_file.content_type,
                'upload_timestamp': uploaded_file.upload_timestamp,
                'b2_file_path': b2_file_path
            }
            
        except Exception as e:
            logger.error(f"Failed to upload data to B2: {str(e)}")
            raise
    
    def get_file_url(self, b2_file_path: str) -> str:
        """
        Get the public URL for a file in B2
        
        Args:
            b2_file_path: Path of file in B2 bucket
            
        Returns:
            Public URL for the file
        """
        try:
            # Get file info
            file_info = self.bucket.get_file_info_by_name(b2_file_path)
            
            # Generate download URL
            download_url = self.api.get_download_url_for_file_name(self.bucket_name, b2_file_path)
            
            return download_url
            
        except Exception as e:
            logger.error(f"Failed to get URL for {b2_file_path}: {str(e)}")
            raise
    
    def download_file(self, b2_file_path: str, local_file_path: str) -> bool:
        """
        Download a file from B2 to local storage
        
        Args:
            b2_file_path: Path of file in B2 bucket
            local_file_path: Local path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Download file from B2
            self.bucket.download_file_by_name(b2_file_path, local_file_path)
            logger.info(f"Successfully downloaded {b2_file_path} to {local_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {b2_file_path}: {str(e)}")
            return False
    
    def delete_file(self, b2_file_path: str) -> bool:
        """
        Delete a file from B2
        
        Args:
            b2_file_path: Path of file in B2 bucket
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get file info first
            file_info = self.bucket.get_file_info_by_name(b2_file_path)
            
            # Delete file
            self.bucket.delete_file_version(file_info.id_, file_info.file_name)
            logger.info(f"Successfully deleted {b2_file_path} from B2")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete {b2_file_path}: {str(e)}")
            return False
    
    def file_exists(self, b2_file_path: str) -> bool:
        """
        Check if a file exists in B2
        
        Args:
            b2_file_path: Path of file in B2 bucket
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.bucket.get_file_info_by_name(b2_file_path)
            return True
        except FileNotPresent:
            return False
        except Exception as e:
            logger.error(f"Error checking if file exists {b2_file_path}: {str(e)}")
            return False
    
    def list_files(self, prefix: str = "", max_count: int = 100) -> list:
        """
        List files in B2 bucket with optional prefix
        
        Args:
            prefix: File name prefix to filter by
            max_count: Maximum number of files to return
            
        Returns:
            List of file info dictionaries
        """
        try:
            files = []
            all_files = list(self.bucket.ls())
            
            # Filter by prefix if provided
            if prefix:
                all_files = [f for f in all_files if f.file_name.startswith(prefix)]
            
            # Limit to max_count
            limited_files = all_files[:max_count]
            
            for file_info in limited_files:
                files.append({
                    'file_name': file_info.file_name,
                    'content_length': file_info.content_length,
                    'upload_timestamp': file_info.upload_timestamp,
                    'content_type': file_info.content_type
                })
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {str(e)}")
            return []
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension"""
        return self._get_content_type_from_path(file_path)
    
    def _get_content_type_from_path(self, file_path: str) -> str:
        """Get content type based on file path/name"""
        ext = os.path.splitext(file_path.lower())[1]
        
        content_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv',
            '.mkv': 'video/x-matroska',
            '.m3u8': 'application/vnd.apple.mpegurl',
            '.ts': 'video/MP2T',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.wav': 'audio/wav'
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def create_temp_file(self, file_data: bytes, suffix: str = None) -> str:
        """
        Create a temporary file for processing
        
        Args:
            file_data: File data as bytes
            suffix: File extension suffix
            
        Returns:
            Path to temporary file
        """
        try:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file.write(file_data)
            temp_file.close()
            
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Failed to create temporary file: {str(e)}")
            raise
    
    def cleanup_temp_file(self, temp_file_path: str):
        """
        Clean up temporary file
        
        Args:
            temp_file_path: Path to temporary file
        """
        try:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup temporary file {temp_file_path}: {str(e)}")

# Global B2 storage service instance
b2_storage = None

def get_b2_storage() -> B2StorageService:
    """Get or create B2 storage service instance"""
    global b2_storage
    if b2_storage is None:
        b2_storage = B2StorageService()
    return b2_storage
