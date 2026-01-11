# Production Deployment Checklist

## Issue: Video Upload Failing with Redis Connection Error

**Error Message:**
```json
{
    "error": "Error 111 connecting to localhost:6379. Connection refused."
}
```

**Root Cause:** Redis (task queue backend) is not running on the production server.

---

## Quick Fix (Production Server)

### Step 1: Check if Redis is installed
```bash
redis-cli --version
```

If not installed:
```bash
sudo apt update
sudo apt install redis-server -y
```

### Step 2: Start Redis
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server  # Auto-start on boot
```

### Step 3: Verify Redis is running
```bash
redis-cli ping
# Expected output: PONG
```

### Step 4: Check Redis connection from your app
```bash
cd /path/to/ocpac-api
python3 check_redis.py
```

### Step 5: Restart your application
```bash
sudo systemctl restart ocpac-api  # Or your service name
# Or if using gunicorn directly:
pkill gunicorn && ./start_flask_app.sh
```

### Step 6: Start/Restart Celery Worker
```bash
# Check if Celery worker is running
ps aux | grep celery

# If not running, start it:
celery -A celery_config.celery worker --loglevel=info --concurrency=2 --pool=prefork

# Or use the startup script if available:
./start_celery_worker.sh
```

---

## Changes Made to Code

### 1. Enhanced Error Handling (`studies/controllers/subtopic_materials_controller.py`)
- Added graceful error handling for Redis connection failures
- Returns HTTP 503 with clear error message when Redis is unavailable
- Cleans up uploaded files and database records on failure
- Updates material status to 'failed' when queue is unavailable

**What users see now:**
```json
{
    "error": "Video processing service is currently unavailable. Please ensure Redis and Celery worker are running.",
    "details": "Error 111 connecting to localhost:6379. Connection refused."
}
```

### 2. Redis Password Support (`celery_config.py`)
- Added support for Redis password authentication
- Reads `REDIS_PASSWORD` from environment variables
- Builds appropriate Redis URL with or without authentication

### 3. Diagnostic Tools
- **`check_redis.py`**: Quick script to diagnose Redis connection issues
- **`REDIS_SETUP.md`**: Comprehensive Redis setup guide

---

## Environment Variables

Add to your `.env` file on production:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Leave empty if no password, or set a strong password

# If Redis is on a different server:
# REDIS_HOST=redis.example.com
# REDIS_PORT=6379
# REDIS_PASSWORD=your_strong_password
```

---

## Production Services Setup

### Redis Service
```bash
# Check status
sudo systemctl status redis-server

# Start/Stop/Restart
sudo systemctl start redis-server
sudo systemctl stop redis-server
sudo systemctl restart redis-server

# View logs
sudo journalctl -u redis-server -f
```

### Celery Worker Service
Create `/etc/systemd/system/celery-ocpac.service`:
```ini
[Unit]
Description=Celery Worker for OCPAC Video Processing
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/ocpac-api
Environment="PATH=/var/www/ocpac-api/venv/bin"
ExecStart=/var/www/ocpac-api/venv/bin/celery -A celery_config.celery worker \
    --loglevel=info \
    --concurrency=2 \
    --pool=prefork \
    --logfile=/var/log/celery/ocpac-worker.log \
    --pidfile=/var/run/celery/ocpac-worker.pid \
    --detach

ExecStop=/var/www/ocpac-api/venv/bin/celery -A celery_config.celery control shutdown
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

Create log directory:
```bash
sudo mkdir -p /var/log/celery /var/run/celery
sudo chown www-data:www-data /var/log/celery /var/run/celery
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-ocpac
sudo systemctl start celery-ocpac
sudo systemctl status celery-ocpac
```

---

## Testing After Deployment

### 1. Test Redis
```bash
redis-cli ping
# Expected: PONG
```

### 2. Test Python Redis Connection
```bash
python3 check_redis.py
# Expected: ✓ Successfully connected to Redis!
```

### 3. Test Celery Worker
```bash
celery -A celery_config.celery inspect active
# Should list active workers
```

### 4. Test Video Upload
Upload a video through the API and monitor:
```bash
# Watch Celery logs
tail -f /var/log/celery/ocpac-worker.log

# Check queue status
redis-cli llen video_processing

# Check material processing status in database
mysql -u ocpac -p -e "SELECT id, name, processing_status, processing_progress FROM subtopic_materials ORDER BY id DESC LIMIT 5;"
```

---

## Monitoring

### Check Queue Status
```bash
# Queue length
redis-cli llen video_processing

# View all queues
redis-cli keys "*"
```

### Check Active Tasks
```bash
celery -A celery_config.celery inspect active
celery -A celery_config.celery inspect registered
```

### Check Worker Status
```bash
celery -A celery_config.celery inspect stats
```

### View Processing Status Dashboard
```bash
python3 celery_dashboard.py
```

---

## Troubleshooting

### Video uploads still failing after Redis is started
1. **Restart the Flask application** to pick up Redis connection
2. **Check if Celery worker is running**: `ps aux | grep celery`
3. **Start Celery worker if not running**: `celery -A celery_config.celery worker --loglevel=info`

### Celery worker crashes frequently
1. Check memory usage: `free -h`
2. Reduce concurrency: Edit `celery_config.py` and set `worker_concurrency=1`
3. Check logs: `tail -f /var/log/celery/ocpac-worker.log`

### Videos stuck in "pending" status
1. Check if Celery worker is running: `ps aux | grep celery`
2. Check queue: `redis-cli llen video_processing`
3. Inspect active tasks: `celery -A celery_config.celery inspect active`
4. Check for errors: `tail -f /var/log/celery/ocpac-worker.log`

### Redis memory issues
```bash
# Check memory usage
redis-cli info memory

# Set max memory limit (e.g., 1GB)
redis-cli config set maxmemory 1gb
redis-cli config set maxmemory-policy allkeys-lru

# Make permanent: edit /etc/redis/redis.conf
```

---

## Security Best Practices

### 1. Set Redis Password
Edit `/etc/redis/redis.conf`:
```
requirepass YOUR_STRONG_PASSWORD_HERE
```

Update `.env`:
```
REDIS_PASSWORD=YOUR_STRONG_PASSWORD_HERE
```

### 2. Bind Redis to Localhost Only
Edit `/etc/redis/redis.conf`:
```
bind 127.0.0.1
```

### 3. Disable Dangerous Commands
Edit `/etc/redis/redis.conf`:
```
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

### 4. Enable Redis Protected Mode
Edit `/etc/redis/redis.conf`:
```
protected-mode yes
```

After changes:
```bash
sudo systemctl restart redis-server
```

---

## Performance Tuning

### For Large Video Files

Edit `celery_config.py`:
```python
worker_max_memory_per_child=2000000,  # 2GB
task_time_limit=7200,  # 2 hours
worker_concurrency=1,  # Process one video at a time
```

### Redis Persistence
Edit `/etc/redis/redis.conf`:
```
save 900 1
save 300 10
save 60 10000
```

---

## Contact & Support

If issues persist after following this guide:
1. Check `/var/log/celery/ocpac-worker.log` for errors
2. Run `python3 check_redis.py` for diagnostic information
3. Check Redis logs: `sudo journalctl -u redis-server -n 100`

