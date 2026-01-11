#!/usr/bin/env python3
"""
Test script for B2 integration
This script helps verify that B2 credentials are properly configured
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_b2_credentials():
    """Test if B2 credentials are properly configured"""
    print("🔍 Testing B2 Configuration...")
    print("=" * 50)
    
    # Check required environment variables
    required_vars = [
        'B2_BUCKET_NAME',
        'B2_APPLICATION_KEY_ID', 
        'B2_APPLICATION_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            # Mask sensitive values
            if 'KEY' in var:
                masked_value = value[:8] + '*' * (len(value) - 12) + value[-4:]
                print(f"✅ {var}: {masked_value}")
            else:
                print(f"✅ {var}: {value}")
    
    if missing_vars:
        print("\n❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 Please set these environment variables:")
        print("   export B2_BUCKET_NAME='your-bucket-name'")
        print("   export B2_APPLICATION_KEY_ID='your-key-id'")
        print("   export B2_APPLICATION_KEY='your-application-key'")
        return False
    
    print("\n✅ All B2 environment variables are configured!")
    return True

def test_b2_connection():
    """Test B2 connection and bucket access"""
    print("\n🔗 Testing B2 Connection...")
    print("=" * 50)
    
    try:
        from storage.b2_storage_service import get_b2_storage
        
        # Initialize B2 storage service
        b2_storage = get_b2_storage()
        print("✅ Successfully connected to B2")
        
        # Test bucket access
        bucket_name = os.getenv('B2_BUCKET_NAME')
        print(f"✅ Successfully accessed bucket: {bucket_name}")
        
        # Test listing files (first 5)
        files = b2_storage.list_files(max_count=5)
        print(f"✅ Successfully listed files in bucket ({len(files)} files found)")
        
        if files:
            print("📁 Sample files in bucket:")
            for file in files[:3]:  # Show first 3 files
                print(f"   - {file['file_name']} ({file['content_length']} bytes)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to connect to B2: {str(e)}")
        print("\n🔧 Troubleshooting tips:")
        print("   1. Verify your B2 credentials are correct")
        print("   2. Check if your B2 bucket exists and is accessible")
        print("   3. Ensure your application key has proper permissions")
        print("   4. Check your internet connection")
        return False

def test_b2_upload():
    """Test B2 file upload functionality"""
    print("\n📤 Testing B2 Upload...")
    print("=" * 50)
    
    try:
        from storage.b2_storage_service import get_b2_storage
        import tempfile
        
        b2_storage = get_b2_storage()
        
        # Create a test file
        test_content = b"Hello B2! This is a test file for OCPAC video storage integration."
        test_file_path = "test_b2_integration.txt"
        
        # Upload test file
        b2_path = f"test/{test_file_path}"
        result = b2_storage.upload_file_data(test_content, b2_path, 'text/plain')
        
        print(f"✅ Successfully uploaded test file to B2")
        print(f"   📁 B2 Path: {b2_path}")
        print(f"   📊 File ID: {result['file_id']}")
        print(f"   📏 Size: {result['content_length']} bytes")
        
        # Test file existence
        if b2_storage.file_exists(b2_path):
            print("✅ File exists check passed")
        else:
            print("❌ File exists check failed")
            return False
        
        # Test getting file URL
        file_url = b2_storage.get_file_url(b2_path)
        print(f"✅ File URL generated: {file_url[:50]}...")
        
        # Clean up test file
        if b2_storage.delete_file(b2_path):
            print("✅ Test file cleanup successful")
        else:
            print("⚠️  Test file cleanup failed (you may need to delete manually)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to test B2 upload: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 OCPAC B2 Integration Test")
    print("=" * 50)
    
    # Test 1: Check credentials
    if not test_b2_credentials():
        print("\n❌ B2 credentials test failed. Please configure your environment variables.")
        sys.exit(1)
    
    # Test 2: Test connection
    if not test_b2_connection():
        print("\n❌ B2 connection test failed. Please check your credentials and network.")
        sys.exit(1)
    
    # Test 3: Test upload
    if not test_b2_upload():
        print("\n❌ B2 upload test failed. Please check your bucket permissions.")
        sys.exit(1)
    
    print("\n🎉 All B2 integration tests passed!")
    print("=" * 50)
    print("✅ Your B2 integration is ready for video uploads!")
    print("\n📝 Next steps:")
    print("   1. Start your Flask application")
    print("   2. Use the /upload-hls-b2 endpoint for video uploads")
    print("   3. Monitor video processing in Celery")
    print("   4. Use /stream-b2 endpoints for video playback")

if __name__ == "__main__":
    main()
