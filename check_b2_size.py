#!/usr/bin/env python3
"""
Script to check B2 storage file sizes for a specific material
"""
import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_b2_file_sizes(material_id):
    """Check the actual file sizes in B2 storage for a material"""
    
    # Get material info from database
    import pymysql
    
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'ocpac',
        'charset': 'utf8mb4',
        'autocommit': True,
        'port': 3306
    }
    
    connection = pymysql.connect(**DB_CONFIG)
    
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT id, name, file_size, b2_material_path, processing_status
            FROM subtopic_materials 
            WHERE id = %s
            """
            cursor.execute(sql, (material_id,))
            result = cursor.fetchone()
            
            if not result:
                print(f"Material {material_id} not found")
                return
                
            material_id, name, file_size, b2_path, status = result
            print(f"Material {material_id}: {name}")
            print(f"Database file_size: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
            print(f"B2 path: {b2_path}")
            print(f"Status: {status}")
            
            if not b2_path:
                print("No B2 path found")
                return
                
            # Extract base path from B2 path
            base_path = '/'.join(b2_path.split('/')[:-1])  # Remove 'output.m3u8'
            print(f"Base path: {base_path}")
            
            # Try to get manifest content to see segments
            try:
                # Construct B2 public URL
                bucket_name = os.getenv('B2_BUCKET_NAME', 'dcrc-ocpac')
                manifest_url = f"https://f005.backblazeb2.com/file/{bucket_name}/{b2_path}"
                print(f"Manifest URL: {manifest_url}")
                
                response = requests.get(manifest_url, timeout=10)
                if response.status_code == 200:
                    manifest_content = response.text
                    print(f"\nManifest content:")
                    print(manifest_content)
                    
                    # Count segments
                    segments = [line for line in manifest_content.split('\n') if line.endswith('.ts')]
                    print(f"\nFound {len(segments)} segments in manifest")
                    
                    # Try to get size of first few segments
                    total_size = 0
                    for i, segment in enumerate(segments[:5]):  # Check first 5 segments
                        segment_url = f"https://f005.backblazeb2.com/file/{bucket_name}/{base_path}/{segment}"
                        try:
                            head_response = requests.head(segment_url, timeout=5)
                            if head_response.status_code == 200:
                                size = int(head_response.headers.get('content-length', 0))
                                total_size += size
                                print(f"  Segment {i+1}: {size} bytes")
                            else:
                                print(f"  Segment {i+1}: Failed to get size (HTTP {head_response.status_code})")
                        except Exception as e:
                            print(f"  Segment {i+1}: Error - {str(e)}")
                    
                    print(f"\nFirst 5 segments total: {total_size} bytes ({total_size/1024/1024:.2f} MB)")
                    print(f"Estimated total for all {len(segments)} segments: {total_size * len(segments) / 5} bytes")
                    
                else:
                    print(f"Failed to get manifest: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"Error checking B2 files: {str(e)}")
                
    finally:
        connection.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_b2_size.py <material_id>")
        sys.exit(1)
        
    material_id = int(sys.argv[1])
    check_b2_file_sizes(material_id)
