#!/usr/bin/env python3
"""
Celery Real-time Dashboard
Shows live status of Celery tasks and queue
"""

import redis
import pymysql
import time
import os
from datetime import datetime

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ocpac',
    'port': 3306
}

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_queue_info():
    """Get Redis queue information"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        queue_length = r.llen('video_processing')
        return queue_length
    except:
        return "❌ Redis Error"

def get_processing_materials():
    """Get materials currently being processed"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, updated_at
            FROM subtopic_materials 
            WHERE processing_status IN ('processing', 'pending')
            ORDER BY updated_at DESC
            LIMIT 10
        """)
        
        materials = cursor.fetchall()
        conn.close()
        return materials
    except Exception as e:
        return f"❌ DB Error: {e}"

def get_recent_completed():
    """Get recently completed materials"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, updated_at
            FROM subtopic_materials 
            WHERE processing_status = 'completed'
            ORDER BY updated_at DESC
            LIMIT 5
        """)
        
        materials = cursor.fetchall()
        conn.close()
        return materials
    except Exception as e:
        return f"❌ DB Error: {e}"

def format_time(timestamp):
    """Format timestamp for display"""
    if timestamp:
        return timestamp.strftime('%H:%M:%S')
    return 'N/A'

def display_dashboard():
    """Display the monitoring dashboard"""
    clear_screen()
    
    print("🎬 CELERY VIDEO PROCESSING DASHBOARD")
    print("=" * 60)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Queue Status
    queue_length = get_queue_info()
    print(f"📊 QUEUE STATUS: {queue_length} tasks waiting")
    print()
    
    # Processing Materials
    print("🔄 CURRENTLY PROCESSING:")
    materials = get_processing_materials()
    
    if isinstance(materials, str):
        print(f"   {materials}")
    elif materials:
        for material in materials:
            id, name, status, progress, storage, updated = material
            name_short = name[:25] + "..." if len(name) > 25 else name
            print(f"   ID {id:3d}: {name_short:<28} | {status:<10} | {progress:3d}% | {storage}")
            print(f"           Updated: {format_time(updated)}")
    else:
        print("   ✅ No materials currently processing")
    
    print()
    
    # Recent Completed
    print("✅ RECENTLY COMPLETED:")
    completed = get_recent_completed()
    
    if isinstance(completed, str):
        print(f"   {completed}")
    elif completed:
        for material in completed:
            id, name, status, progress, storage, updated = material
            name_short = name[:25] + "..." if len(name) > 25 else name
            print(f"   ID {id:3d}: {name_short:<28} | {status:<10} | {progress:3d}% | {storage}")
            print(f"           Completed: {format_time(updated)}")
    else:
        print("   📭 No recent completions")
    
    print()
    print("Press Ctrl+C to exit")
    print("-" * 60)

def main():
    """Main dashboard loop"""
    try:
        while True:
            display_dashboard()
            time.sleep(5)  # Update every 5 seconds
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped")

if __name__ == "__main__":
    main()
