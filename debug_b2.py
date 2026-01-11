#!/usr/bin/env python3
"""
Debug script for B2 connection issues
"""

import os
from b2sdk.v2 import B2Api

def test_b2_connection():
    print("🔍 Testing B2 Connection...")
    print("=" * 50)
    
    # Get credentials
    bucket_name = os.getenv('B2_BUCKET_NAME')
    key_id = os.getenv('B2_APPLICATION_KEY_ID')
    key = os.getenv('B2_APPLICATION_KEY')
    
    print(f"Bucket Name: {bucket_name}")
    print(f"Key ID: {key_id}")
    print(f"Key: {key[:10]}...{key[-10:]}")
    
    try:
        # Create B2 API instance
        api = B2Api()
        
        print("📡 Attempting to authorize with B2...")
        
        # Try to authorize
        api.authorize_account("production", key_id, key)
        
        print("✅ Successfully authorized with B2!")
        
        # Try to get bucket
        print(f"📦 Attempting to access bucket: {bucket_name}")
        bucket = api.get_bucket_by_name(bucket_name)
        
        print(f"✅ Successfully accessed bucket: {bucket_name}")
        print(f"📊 Bucket ID: {bucket.id_}")
        
        # List some files
        print("\n📁 Listing files in bucket:")
        files = list(bucket.ls())
        print(f"Found {len(files)} files")
        
        for i, file_info in enumerate(files[:5]):  # Show first 5 files
            try:
                # Handle both tuple and object formats
                if hasattr(file_info, 'file_name'):
                    print(f"  {i+1}. {file_info.file_name} ({file_info.content_length} bytes)")
                elif isinstance(file_info, tuple) and len(file_info) >= 2:
                    print(f"  {i+1}. {file_info[0]} ({file_info[1]} bytes)")
                else:
                    print(f"  {i+1}. {file_info}")
            except Exception as e:
                print(f"❌ Error: {e}")
                print(f"Error type: {type(e).__name__}")
                print(f"File info type: {type(file_info)}")
                print(f"File info: {file_info}")
                break
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        
        # Try to get more details about the error
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        
        return False

if __name__ == "__main__":
    test_b2_connection()
