"""
Test script for specific VdoCipher video
Tests video details retrieval and OTP generation
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.vdocipher_service import VdoCipherService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Your test video ID
TEST_VIDEO_ID = "d79887007d3247c681207a85edd1735f"

def test_video_operations():
    """Test video operations with your uploaded video"""
    print("🎬 Testing VdoCipher Video Operations...")
    print("=" * 60)
    
    try:
        # Initialize service
        vdocipher = VdoCipherService()
        
        # Test 1: Get video details
        print(f"\n1. Fetching video details for ID: {TEST_VIDEO_ID}")
        print("-" * 60)
        
        video_details = vdocipher.get_video_details(TEST_VIDEO_ID)
        
        print(f"   ✅ Video found!")
        print(f"   📝 Title: {video_details.get('title')}")
        print(f"   📊 Status: {video_details.get('status')}")
        print(f"   ⏱️  Duration: {video_details.get('length', 0)} seconds")
        print(f"   🖼️  Thumbnail: {video_details.get('thumbnail', 'N/A')}")
        
        # Check if video is ready
        if video_details.get('status') != 'ready':
            print(f"\n   ⚠️  Video is still processing (status: {video_details.get('status')})")
            print("   Please wait a few minutes and run this test again.")
            return False
        
        # Test 2: Generate OTP
        print(f"\n2. Generating OTP for video playback...")
        print("-" * 60)
        
        otp_data = vdocipher.generate_otp(
            video_id=TEST_VIDEO_ID,
            user_id=1,
            user_email="test@dcrc.ac.tz",
            user_name="Test User",
            ip_address=None  # No IP restriction for testing
        )
        
        print(f"   ✅ OTP generated successfully!")
        print(f"   🔑 OTP: {otp_data.get('otp')[:20]}...")
        print(f"   📦 Playback Info: {otp_data.get('playbackInfo')[:30]}...")
        
        # Test 3: Summary
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\n📋 Next Steps:")
        print("   1. Update database with video ID")
        print("   2. Create API endpoints")
        print("   3. Integrate frontend player")
        print("\n🎉 Your VdoCipher integration is working perfectly!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nPossible issues:")
        print("1. Video might still be processing (wait a few minutes)")
        print("2. Video ID might be incorrect")
        print("3. API credentials might be wrong")
        return False


if __name__ == "__main__":
    success = test_video_operations()
    sys.exit(0 if success else 1)

