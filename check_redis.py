#!/usr/bin/env python3
"""
Redis Connection Checker
Quickly diagnose Redis connection issues
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

print("="*60)
print("REDIS CONNECTION CHECKER")
print("="*60)
print(f"Host: {REDIS_HOST}")
print(f"Port: {REDIS_PORT}")
print(f"Password: {'***' if REDIS_PASSWORD else '(none)'}")
print("="*60)

# Try to import redis
try:
    import redis
    print("✓ Redis Python package is installed")
except ImportError:
    print("✗ Redis Python package is NOT installed")
    print("  Install with: pip install redis")
    sys.exit(1)

# Try to connect to Redis
try:
    if REDIS_PASSWORD:
        r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            password=REDIS_PASSWORD,
            decode_responses=True
        )
    else:
        r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            decode_responses=True
        )
    
    # Test connection
    response = r.ping()
    if response:
        print("✓ Successfully connected to Redis!")
        
        # Get Redis info
        info = r.info('server')
        print(f"\nRedis Version: {info.get('redis_version', 'unknown')}")
        print(f"Uptime (days): {info.get('uptime_in_days', 'unknown')}")
        
        # Check memory
        memory_info = r.info('memory')
        used_memory = memory_info.get('used_memory_human', 'unknown')
        print(f"Memory Used: {used_memory}")
        
        # Check if Celery queues exist
        print("\n" + "-"*60)
        print("CELERY QUEUE STATUS")
        print("-"*60)
        
        # Check default queue
        queue_length = r.llen('celery')
        print(f"Default queue (celery): {queue_length} tasks")
        
        # Check video processing queue
        video_queue_length = r.llen('video_processing')
        print(f"Video processing queue: {video_queue_length} tasks")
        
        print("\n" + "="*60)
        print("✓ Redis is working correctly!")
        print("="*60)
        sys.exit(0)
    else:
        print("✗ Redis PING failed")
        sys.exit(1)
        
except redis.ConnectionError as e:
    print(f"✗ Connection Error: {e}")
    print("\nPossible solutions:")
    print("1. Redis is not running:")
    print("   - Ubuntu/Debian: sudo systemctl start redis-server")
    print("   - Check status: sudo systemctl status redis-server")
    print("\n2. Redis is running on a different host/port:")
    print("   - Update REDIS_HOST and REDIS_PORT in .env file")
    print("\n3. Firewall is blocking the connection:")
    print("   - Check firewall rules: sudo ufw status")
    print("   - Allow port: sudo ufw allow 6379")
    sys.exit(1)
    
except redis.AuthenticationError as e:
    print(f"✗ Authentication Error: {e}")
    print("\nPossible solutions:")
    print("1. Redis requires a password but none was provided:")
    print("   - Add REDIS_PASSWORD to .env file")
    print("\n2. The password is incorrect:")
    print("   - Check Redis password in /etc/redis/redis.conf")
    print("   - Update REDIS_PASSWORD in .env file")
    sys.exit(1)
    
except Exception as e:
    print(f"✗ Unexpected Error: {e}")
    print(f"\nError type: {type(e).__name__}")
    sys.exit(1)

