"""
Test script for VdoCipher integration
Run this to verify your API credentials and connection
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.vdocipher_service import VdoCipherService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_vdocipher_connection():
    """Test VdoCipher API connection and credentials"""
    print("🔍 Testing VdoCipher Integration...")
    print("-" * 50)
    
    try:
        # Initialize service
        print("1. Initializing VdoCipher service...")
        vdocipher = VdoCipherService()
        print("   ✅ Service initialized")
        
        # Test connection
        print("\n2. Testing API connection...")
        if vdocipher.test_connection():
            print("   ✅ Connection successful!")
        else:
            print("   ❌ Connection failed")
            return False
        
        # Test getting video list (should work even if empty)
        print("\n3. Testing API credentials...")
        import requests
        response = requests.get(
            f"{vdocipher.BASE_URL}/videos",
            headers=vdocipher.headers,
            params={'limit': 5}
        )
        
        if response.status_code == 200:
            print("   ✅ API credentials valid!")
            videos = response.json()
            print(f"   📊 Found {len(videos.get('rows', []))} videos in your account")
            
            # List videos if any
            if videos.get('rows'):
                print("\n   Your videos:")
                for video in videos.get('rows', []):
                    print(f"   - {video.get('title')} (ID: {video.get('id')})")
        else:
            print(f"   ❌ API credentials invalid (Status: {response.status_code})")
            return False
        
        print("\n" + "=" * 50)
        print("✅ VdoCipher integration test PASSED!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nPlease check:")
        print("1. VDOCIPHER_API_SECRET is set in .env file")
        print("2. API secret is correct (copy from VdoCipher dashboard)")
        print("3. You have internet connection")
        return False


if __name__ == "__main__":
    success = test_vdocipher_connection()
    sys.exit(0 if success else 1)

