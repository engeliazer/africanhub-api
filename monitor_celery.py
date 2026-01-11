#!/usr/bin/env python3
"""
Celery Queue Monitor
Monitors Redis queue, active tasks, and database status
"""

import redis
import pymysql
import time
import json
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

def get_redis_connection():
    """Get Redis connection"""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def get_db_connection():
    """Get MySQL connection"""
    return pymysql.connect(**DB_CONFIG)

def check_queue_status():
    """Check Redis queue status"""
    try:
        r = get_redis_connection()
        
        # Check queue length
        queue_length = r.llen('video_processing')
        
        # Check for active tasks
        active_tasks = r.hgetall('celery-task-meta-*')
        
        print(f"📊 Queue Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Queue Length: {queue_length}")
        print(f"   Active Tasks: {len(active_tasks)}")
        
        return queue_length, len(active_tasks)
    except Exception as e:
        print(f"❌ Redis Error: {e}")
        return None, None

def check_processing_materials():
    """Check materials currently being processed"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get materials in processing state
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, created_at, updated_at
            FROM subtopic_materials 
            WHERE processing_status IN ('processing', 'pending')
            ORDER BY updated_at DESC
        """)
        
        materials = cursor.fetchall()
        
        if materials:
            print(f"\n🔄 Processing Materials ({len(materials)}):")
            for material in materials:
                id, name, status, progress, storage, created, updated = material
                print(f"   ID {id}: {name[:30]}... | {status} | {progress}% | {storage}")
                print(f"      Created: {created} | Updated: {updated}")
        else:
            print("\n✅ No materials currently processing")
        
        conn.close()
        return materials
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return []

def check_stuck_tasks():
    """Check for tasks that might be stuck (processing for > 30 minutes)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find materials processing for more than 30 minutes
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   updated_at, TIMESTAMPDIFF(MINUTE, updated_at, NOW()) as minutes_processing
            FROM subtopic_materials 
            WHERE processing_status = 'processing' 
            AND TIMESTAMPDIFF(MINUTE, updated_at, NOW()) > 30
            ORDER BY updated_at ASC
        """)
        
        stuck_materials = cursor.fetchall()
        
        if stuck_materials:
            print(f"\n⚠️  POTENTIALLY STUCK TASKS ({len(stuck_materials)}):")
            for material in stuck_materials:
                id, name, status, progress, updated, minutes = material
                print(f"   🚨 ID {id}: {name[:30]}... | {status} | {progress}% | {minutes}min")
                print(f"      Last updated: {updated}")
        else:
            print("\n✅ No stuck tasks detected")
        
        conn.close()
        return stuck_materials
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return []

def clear_stuck_tasks():
    """Clear stuck tasks and reset their status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find and reset stuck tasks
        cursor.execute("""
            UPDATE subtopic_materials 
            SET processing_status = 'failed', 
                processing_error = 'Task stuck - cleared by monitor'
            WHERE processing_status = 'processing' 
            AND TIMESTAMPDIFF(MINUTE, updated_at, NOW()) > 30
        """)
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if affected > 0:
            print(f"\n🧹 Cleared {affected} stuck tasks")
        else:
            print("\n✅ No stuck tasks to clear")
            
        return affected
    except Exception as e:
        print(f"❌ Error clearing stuck tasks: {e}")
        return 0

def main():
    """Main monitoring function"""
    print("🔍 Celery Queue Monitor")
    print("=" * 50)
    
    # Check queue status
    queue_length, active_tasks = check_queue_status()
    
    # Check processing materials
    processing_materials = check_processing_materials()
    
    # Check for stuck tasks
    stuck_tasks = check_stuck_tasks()
    
    # Summary
    print(f"\n📈 Summary:")
    print(f"   Queue: {queue_length} tasks")
    print(f"   Processing: {len(processing_materials)} materials")
    print(f"   Stuck: {len(stuck_tasks)} materials")
    
    # Auto-clear stuck tasks if any
    if stuck_tasks:
        print(f"\n🤖 Auto-clearing stuck tasks...")
        cleared = clear_stuck_tasks()
        if cleared > 0:
            print(f"✅ Cleared {cleared} stuck tasks")

if __name__ == "__main__":
    main()
