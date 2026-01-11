"""
Monitoring API Routes
Provides endpoints for monitoring Celery tasks and queue status
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import redis
import pymysql
from datetime import datetime, timedelta
import json
import os
import subprocess

monitoring_bp = Blueprint('monitoring', __name__)

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'ocpac',
    'password': 'oCpAc@2025',
    'database': 'ocpac',
    'port': 3306
}

def get_redis_connection():
    """Get Redis connection"""
    try:
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    except Exception as e:
        return None

def get_db_connection():
    """Get MySQL connection"""
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        return None

@monitoring_bp.route('/monitoring/queue-status', methods=['GET'])
@jwt_required()
def get_queue_status():
    """Get current queue status"""
    try:
        r = get_redis_connection()
        if not r:
            return jsonify({"error": "Redis connection failed"}), 500
        
        # Get queue information
        queue_length = r.llen('video_processing')
        
        # Get active tasks (approximate)
        active_tasks = len(r.keys('celery-task-meta-*'))
        
        return jsonify({
            "queue_length": queue_length,
            "active_tasks": active_tasks,
            "timestamp": datetime.now().isoformat(),
            "status": "healthy" if queue_length < 10 else "busy"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/processing-materials', methods=['GET'])
@jwt_required()
def get_processing_materials():
    """Get materials currently being processed"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Get materials in processing state
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, created_at, updated_at,
                   TIMESTAMPDIFF(MINUTE, updated_at, NOW()) as minutes_processing
            FROM subtopic_materials 
            WHERE processing_status IN ('processing', 'pending')
            ORDER BY updated_at DESC
        """)
        
        materials = []
        for row in cursor.fetchall():
            id, name, status, progress, storage, created, updated, minutes = row
            materials.append({
                "id": id,
                "name": name,
                "status": status,
                "progress": progress,
                "storage_location": storage,
                "created_at": created.isoformat() if created else None,
                "updated_at": updated.isoformat() if updated else None,
                "minutes_processing": minutes,
                "is_stuck": minutes > 30
            })
        
        conn.close()
        
        return jsonify({
            "materials": materials,
            "count": len(materials),
            "stuck_count": len([m for m in materials if m["is_stuck"]]),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/recent-completed', methods=['GET'])
@jwt_required()
def get_recent_completed():
    """Get recently completed materials"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Get recently completed materials
        limit = request.args.get('limit', 10, type=int)
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, updated_at
            FROM subtopic_materials 
            WHERE processing_status = 'completed'
            ORDER BY updated_at DESC
            LIMIT %s
        """, (limit,))
        
        materials = []
        for row in cursor.fetchall():
            id, name, status, progress, storage, updated = row
            materials.append({
                "id": id,
                "name": name,
                "status": status,
                "progress": progress,
                "storage_location": storage,
                "completed_at": updated.isoformat() if updated else None
            })
        
        conn.close()
        
        return jsonify({
            "materials": materials,
            "count": len(materials),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/stuck-tasks', methods=['GET'])
@jwt_required()
def get_stuck_tasks():
    """Get tasks that might be stuck (processing for > 30 minutes)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
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
        
        stuck_tasks = []
        for row in cursor.fetchall():
            id, name, status, progress, updated, minutes = row
            stuck_tasks.append({
                "id": id,
                "name": name,
                "status": status,
                "progress": progress,
                "updated_at": updated.isoformat() if updated else None,
                "minutes_processing": minutes
            })
        
        conn.close()
        
        return jsonify({
            "stuck_tasks": stuck_tasks,
            "count": len(stuck_tasks),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/clear-stuck-tasks', methods=['POST'])
@jwt_required()
def clear_stuck_tasks():
    """Clear stuck tasks and reset their status"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
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
        
        return jsonify({
            "message": f"Cleared {affected} stuck tasks",
            "affected_count": affected,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/clear-queue', methods=['POST'])
@jwt_required()
def clear_queue():
    """Clear the entire Redis queue"""
    try:
        r = get_redis_connection()
        if not r:
            return jsonify({"error": "Redis connection failed"}), 500
        
        # Get queue length before clearing
        queue_length = r.llen('video_processing')
        
        # Clear the queue
        r.delete('video_processing')
        
        return jsonify({
            "message": f"Cleared {queue_length} tasks from queue",
            "cleared_count": queue_length,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/test', methods=['GET'])
def test_monitoring():
    """Test endpoint without authentication"""
    return jsonify({
        "message": "Monitoring API is working!",
        "timestamp": datetime.now().isoformat()
    })

@monitoring_bp.route('/monitoring/restart-workers', methods=['POST'])
@jwt_required()
def restart_workers():
    """Securely restart Celery workers (kill and relaunch script)."""
    try:
        # Optional extra safety: admin key
        admin_key = os.getenv('ADMIN_API_KEY')
        provided = request.headers.get('X-Admin-Key') or request.args.get('admin_key')
        if admin_key and provided != admin_key:
            return jsonify({"error": "Forbidden"}), 403

        # Kill existing celery processes
        try:
            result = subprocess.run(['pkill', '-f', 'celery'], capture_output=True, text=True)
            print(f"Kill result: {result.returncode}, stdout: {result.stdout}, stderr: {result.stderr}")
        except Exception as e:
            print(f"Kill error: {e}")

        # Wait a moment for processes to fully terminate
        import time
        time.sleep(2)

        # Relaunch in background with error capture
        script_path = os.path.join(os.getcwd(), 'start_celery_worker.sh')
        if not os.path.exists(script_path):
            return jsonify({"error": "start_celery_worker.sh not found"}), 500

        # Make script executable
        os.chmod(script_path, 0o755)

        # Start with error capture for debugging
        process = subprocess.Popen(
            ['bash', script_path], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )

        # Give it a moment to start
        time.sleep(3)

        # Check if process is still running
        if process.poll() is not None:
            # Process exited, get error output
            stdout, stderr = process.communicate()
            return jsonify({
                "error": f"Worker startup failed. Return code: {process.returncode}",
                "stdout": stdout,
                "stderr": stderr
            }), 500

        # Check if celery processes are actually running
        try:
            result = subprocess.run(['pgrep', '-f', 'celery'], capture_output=True, text=True)
            if result.returncode != 0:
                return jsonify({
                    "error": "No celery processes found after restart",
                    "pgrep_output": result.stdout
                }), 500
        except Exception as e:
            return jsonify({"error": f"Failed to verify workers: {str(e)}"}), 500

        return jsonify({
            "message": "Workers restart successful",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@monitoring_bp.route('/monitoring/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Get complete monitoring dashboard data"""
    try:
        # Get all monitoring data
        r = get_redis_connection()
        conn = get_db_connection()
        
        if not r or not conn:
            return jsonify({"error": "Connection failed"}), 500
        
        # Queue status
        queue_length = r.llen('video_processing')
        active_tasks = len(r.keys('celery-task-meta-*'))
        
        # Database status
        cursor = conn.cursor()
        
        # Processing materials
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, updated_at,
                   TIMESTAMPDIFF(MINUTE, updated_at, NOW()) as minutes_processing
            FROM subtopic_materials 
            WHERE processing_status IN ('processing', 'pending')
            ORDER BY updated_at DESC
        """)
        
        processing_materials = []
        for row in cursor.fetchall():
            id, name, status, progress, storage, updated, minutes = row
            processing_materials.append({
                "id": id,
                "name": name,
                "status": status,
                "progress": progress,
                "storage_location": storage,
                "updated_at": updated.isoformat() if updated else None,
                "minutes_processing": minutes,
                "is_stuck": minutes > 30
            })
        
        # Recent completed
        cursor.execute("""
            SELECT id, name, processing_status, processing_progress, 
                   storage_location, updated_at
            FROM subtopic_materials 
            WHERE processing_status = 'completed'
            ORDER BY updated_at DESC
            LIMIT 5
        """)
        
        recent_completed = []
        for row in cursor.fetchall():
            id, name, status, progress, storage, updated = row
            recent_completed.append({
                "id": id,
                "name": name,
                "status": status,
                "progress": progress,
                "storage_location": storage,
                "completed_at": updated.isoformat() if updated else None
            })
        
        # Statistics
        cursor.execute("SELECT COUNT(*) FROM subtopic_materials WHERE processing_status = 'processing'")
        processing_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM subtopic_materials WHERE processing_status = 'completed'")
        completed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM subtopic_materials WHERE processing_status = 'failed'")
        failed_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "queue": {
                "length": queue_length,
                "active_tasks": active_tasks,
                "status": "healthy" if queue_length < 10 else "busy"
            },
            "materials": {
                "processing": processing_materials,
                "recent_completed": recent_completed,
                "counts": {
                    "processing": processing_count,
                    "completed": completed_count,
                    "failed": failed_count
                }
            },
            "stuck_tasks": {
                "count": len([m for m in processing_materials if m["is_stuck"]]),
                "tasks": [m for m in processing_materials if m["is_stuck"]]
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
