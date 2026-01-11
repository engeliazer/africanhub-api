"""
VdoCipher Service for video DRM integration
Handles video upload, OTP generation, and video management
"""

import requests
import os
import json
import time
from typing import Dict, Optional
from functools import wraps


def retry_on_failure(max_retries=3, delay=2):
    """
    Decorator to retry failed API calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)  # Exponential backoff
                        print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"All {max_retries} attempts failed")
            
            raise last_exception
        return wrapper
    return decorator


class VdoCipherService:
    """Service class for VdoCipher API interactions"""
    
    BASE_URL = "https://dev.vdocipher.com/api"
    
    def __init__(self):
        """Initialize VdoCipher service with API credentials"""
        self.api_secret = os.getenv('VDOCIPHER_API_SECRET')
        
        if not self.api_secret:
            raise ValueError("VDOCIPHER_API_SECRET not set in environment variables")
        
        self.headers = {
            'Authorization': f'Apisecret {self.api_secret}',
            'Content-Type': 'application/json'
        }
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_video_details(self, video_id: str) -> Dict:
        """
        Get video details including status, duration, thumbnails
        
        Args:
            video_id: VdoCipher video ID
            
        Returns:
            Dict with video details
            
        Raises:
            Exception: If API call fails
        """
        url = f"{self.BASE_URL}/videos/{video_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception("VdoCipher API timeout")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Video {video_id} not found in VdoCipher")
            elif e.response.status_code == 401:
                raise Exception("Invalid VdoCipher API credentials")
            else:
                raise Exception(f"VdoCipher API error: {e.response.text}")
    
    @retry_on_failure(max_retries=3, delay=2)
    def generate_otp(self, video_id: str, user_id: int, user_email: str, 
                     user_name: str, ip_address: str = None) -> Dict:
        """
        Generate OTP and playback info for video playback with user watermark
        
        Args:
            video_id: VdoCipher video ID
            user_id: Application user ID
            user_email: User email for watermarking
            user_name: User name for watermarking
            ip_address: Optional IP address restriction
            
        Returns:
            Dict with OTP and playback info
            
        Raises:
            Exception: If OTP generation fails
        """
        url = f"{self.BASE_URL}/videos/{video_id}/otp"
        
        # Create watermark annotation
        payload = {
            "annotate": json.dumps([
                {
                    "type": "rtext",  # Rolling text watermark
                    "text": f"{user_name} ({user_email})",
                    "alpha": "0.60",  # 60% opacity
                    "color": "0xFF0000",  # Red color
                    "size": "15",  # Font size
                    "interval": "5000"  # Show every 5 seconds
                }
            ])
        }
        
        # Optional: Restrict to specific IP address
        if ip_address:
            payload["ip"] = ip_address
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception("VdoCipher API timeout while generating OTP")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Video {video_id} not found in VdoCipher")
            elif e.response.status_code == 401:
                raise Exception("Invalid VdoCipher API credentials")
            elif e.response.status_code == 429:
                raise Exception("VdoCipher rate limit exceeded")
            else:
                raise Exception(f"Failed to generate OTP: {e.response.text}")
    
    @retry_on_failure(max_retries=3, delay=2)
    def upload_video(self, title: str, folder_id: Optional[str] = None) -> Dict:
        """
        Get upload credentials for a new video
        
        Args:
            title: Video title
            folder_id: Optional VdoCipher folder ID
            
        Returns:
            Dict with upload credentials including videoId and upload URL
            
        Raises:
            Exception: If upload credential request fails
        """
        url = f"{self.BASE_URL}/videos"
        
        # VdoCipher expects title as query parameter, not in body
        params = {
            "title": title
        }
        
        if folder_id:
            params["folderId"] = folder_id
        
        try:
            response = requests.put(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            # Log response for debugging
            print(f"VdoCipher upload response: {response_data}")
            
            return response_data
        except requests.exceptions.Timeout:
            raise Exception("VdoCipher API timeout")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Invalid VdoCipher API credentials")
            elif e.response.status_code == 429:
                raise Exception("VdoCipher rate limit exceeded")
            else:
                raise Exception(f"VdoCipher API error: {e.response.text}")
    
    @retry_on_failure(max_retries=3, delay=2)
    def delete_video(self, video_id: str) -> bool:
        """
        Delete video from VdoCipher
        
        Note: VdoCipher performs a soft delete (moves to trash).
        Videos in trash can be restored from the dashboard.
        To permanently delete, you must empty trash manually in VdoCipher dashboard.
        
        Args:
            video_id: VdoCipher video ID
            
        Returns:
            True if deletion successful
            
        Raises:
            Exception: If deletion fails
        """
        url = f"{self.BASE_URL}/videos/{video_id}"
        
        try:
            response = requests.delete(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Log response for debugging
            print(f"VdoCipher delete response status: {response.status_code}")
            if response.text:
                print(f"VdoCipher delete response: {response.text}")
            
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Video already deleted or doesn't exist
                return True
            else:
                raise Exception(f"Failed to delete video: {e.response.text}")
    
    def test_connection(self) -> bool:
        """
        Test VdoCipher API connection
        
        Returns:
            True if connection successful
        """
        try:
            url = f"{self.BASE_URL}/videos"
            response = requests.get(
                url,
                headers=self.headers,
                params={'limit': 1},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"VdoCipher connection test failed: {str(e)}")
            return False

