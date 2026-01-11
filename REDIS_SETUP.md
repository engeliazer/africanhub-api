# Redis Setup Guide for Production

## Problem
Video upload endpoints return error: `"Error 111 connecting to localhost:6379. Connection refused."`

This means Redis is not running. Redis is required for the Celery task queue that processes video uploads.

---

## Solution 1: Install and Start Redis (Ubuntu/Debian)

### 1. Install Redis
```bash
sudo apt update
sudo apt install redis-server -y
```

### 2. Configure Redis
Edit Redis configuration:
```bash
sudo nano /etc/redis/redis.conf
```

Find and update:
```
supervised systemd
```

### 3. Start Redis Service
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server  # Auto-start on boot
```

### 4. Verify Redis is Running
```bash
redis-cli ping
# Should return: PONG

# Check status
sudo systemctl status redis-server
```

### 5. Test Connection
```bash
redis-cli
> ping
PONG
> exit
```

---

## Solution 2: Use Remote Redis

If you have Redis running on a different server, configure environment variables:

### 1. Create/Edit `.env` file:
```bash
nano .env
```

### 2. Add Redis configuration:
```
REDIS_HOST=your-redis-host.com
REDIS_PORT=6379
```

### 3. Restart your Flask application:
```bash
sudo systemctl restart ocpac-api  # Or your service name
```

---

## Start Celery Worker

After Redis is running, you need to start the Celery worker:

```bash
# Navigate to project directory
cd /path/to/ocpac-api

# Start Celery worker
celery -A celery_config.celery worker --loglevel=info --concurrency=2 --pool=prefork

# Or use the provided script:
./start_celery_worker.sh
```

### Run Celery as a Service (Production)

Create systemd service file:
```bash
sudo nano /etc/systemd/system/celery-ocpac.service
```

Add:
```ini
[Unit]
Description=Celery Worker for OCPAC
After=network.target redis-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/ocpac-api
Environment="PATH=/path/to/ocpac-api/venv/bin"
ExecStart=/path/to/ocpac-api/venv/bin/celery -A celery_config.celery worker --loglevel=info --concurrency=2 --pool=prefork --detach

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-ocpac
sudo systemctl start celery-ocpac
sudo systemctl status celery-ocpac
```

---

## Monitoring

### Check Redis Status
```bash
redis-cli info stats
redis-cli info memory
```

### Check Celery Queue
```bash
# From project directory
python3 monitor_celery.py

# Or check with redis-cli
redis-cli llen celery
```

### View Celery Logs
```bash
# If running as service
sudo journalctl -u celery-ocpac -f

# If running manually, check terminal output
```

---

## Troubleshooting

### Redis won't start
```bash
# Check logs
sudo journalctl -u redis-server -n 50

# Check if port is already in use
sudo netstat -tlnp | grep 6379
```

### Celery worker won't start
```bash
# Check for syntax errors
python3 -c "from celery_config import celery; print('OK')"

# Check task imports
python3 -c "from tasks_streamlined import convert_video_to_hls_task; print('OK')"
```

### Permission issues
```bash
# Ensure proper ownership
sudo chown -R www-data:www-data /path/to/ocpac-api/storage

# Ensure writable directories
chmod 755 /path/to/ocpac-api/storage/uploads
```

---

## Security Considerations

### Bind Redis to localhost only (if on same server)
Edit `/etc/redis/redis.conf`:
```
bind 127.0.0.1
```

### Set Redis password (recommended for production)
Edit `/etc/redis/redis.conf`:
```
requirepass your_strong_password_here
```

Update `.env`:
```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_strong_password_here
```

Update `celery_config.py`:
```python
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
redis_url = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0' if REDIS_PASSWORD else f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
```

---

## Quick Test After Setup

1. **Test Redis**:
   ```bash
   redis-cli ping  # Should return PONG
   ```

2. **Test Celery**:
   ```bash
   celery -A celery_config.celery inspect active
   ```

3. **Test Upload**:
   Upload a video through the API and check:
   ```bash
   # Watch logs
   tail -f /var/log/ocpac/celery.log
   
   # Or check database
   mysql -u ocpac -p ocpac -e "SELECT id, name, processing_status FROM subtopic_materials ORDER BY id DESC LIMIT 5;"
   ```

