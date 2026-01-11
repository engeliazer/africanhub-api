# Worker Crash Investigation

## What's Happening
Gunicorn master is running but workers are being killed immediately with SIGTERM. This means workers are crashing during startup.

## Commands to Run on Production

### 1. Check Full Error Logs
```bash
# Check gunicorn error logs
sudo journalctl -u gunicorn-api -n 100 --no-pager

# Or if there's a log file
tail -100 /var/log/gunicorn/error.log
tail -100 /var/log/gunicorn/access.log

# Check for any application errors
ls -la /var/www/ocpac/api.ocpac.dcrc.ac.tz/*.log
```

### 2. Test App Import Manually
```bash
cd /var/www/ocpac/api.ocpac.dcrc.ac.tz

# Activate virtual environment
source venv/bin/activate

# Try to import the app
python3 -c "from wsgi import app; print('✅ Import successful')"
```

This will show the actual error that's causing workers to crash.

### 3. Test with Single Worker in Foreground
```bash
cd /var/www/ocpac/api.ocpac.dcrc.ac.tz
source venv/bin/activate

# Run gunicorn in foreground with debug output
gunicorn --workers 1 --bind unix:/var/www/ocpac/api.ocpac.dcrc.ac.tz/gunicorn.sock --log-level debug wsgi:app
```

Press Ctrl+C after seeing the error, then send me the output.

### 4. Check for Import/Syntax Errors
```bash
cd /var/www/ocpac/api.ocpac.dcrc.ac.tz
source venv/bin/activate

# Check syntax of recently modified files
python3 -m py_compile api/routes/monitoring_routes.py
python3 -m py_compile tasks_streamlined.py
python3 -m py_compile tasks.py
python3 -m py_compile tasks_migration.py
python3 -m py_compile tasks_local.py
python3 -m py_compile tasks_b2.py
python3 -m py_compile studies/controllers/subtopic_materials_controller.py
```

### 5. Check Database Connection
```bash
# Test if app can connect to database
python3 << 'EOF'
import pymysql

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'ocpac',
    'password': 'oCpAc@2025',
    'database': 'ocpac',
    'port': 3306
}

try:
    conn = pymysql.connect(**DB_CONFIG)
    print("✅ Database connection OK")
    conn.close()
except Exception as e:
    print(f"❌ Database error: {e}")
EOF
```

## Most Likely Issues

### Issue 1: Import Error in Modified Files
**Symptom:** Workers crash immediately on startup
**Check:** 
```bash
python3 -c "from app import app"
```

### Issue 2: Database Connection Error on Startup
**Symptom:** Workers crash trying to connect to DB during initialization
**Check:** Database credentials and MySQL service

### Issue 3: Missing Python Dependency
**Symptom:** ImportError or ModuleNotFoundError
**Fix:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Issue 4: Celery Config Error
**Symptom:** Redis connection error during import
**Check:**
```bash
python3 -c "from celery_config import celery; print('OK')"
```

## Quick Diagnostic Script

Run this on production and send me the full output:

```bash
#!/bin/bash
cd /var/www/ocpac/api.ocpac.dcrc.ac.tz
source venv/bin/activate

echo "=== Testing App Import ==="
python3 -c "from wsgi import app; print('✅ wsgi:app import OK')" 2>&1

echo -e "\n=== Testing App Module ==="
python3 -c "from app import app; print('✅ app:app import OK')" 2>&1

echo -e "\n=== Testing Celery Config ==="
python3 -c "from celery_config import celery; print('✅ Celery config OK')" 2>&1

echo -e "\n=== Testing Database Connection ==="
python3 << 'EOF'
import pymysql
try:
    conn = pymysql.connect(host='127.0.0.1', user='ocpac', password='oCpAc@2025', database='ocpac', port=3306)
    print("✅ Database connection OK")
    conn.close()
except Exception as e:
    print(f"❌ Database error: {e}")
EOF

echo -e "\n=== Testing Redis Connection ==="
python3 << 'EOF'
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print("✅ Redis connection OK")
except Exception as e:
    print(f"❌ Redis error: {e}")
EOF

echo -e "\n=== Recent Gunicorn Logs ==="
sudo journalctl -u gunicorn-api -n 50 --no-pager 2>&1 | tail -30

echo -e "\n=== Python Version ==="
python3 --version

echo -e "\n=== Installed Packages ==="
pip list | grep -E "Flask|gunicorn|celery|pymysql|redis"
```

Save this as `diagnose.sh`, make it executable with `chmod +x diagnose.sh`, then run `./diagnose.sh`

## Temporary Workaround

While we debug, you can try reducing workers to see if it helps:

```bash
# Edit the service file
sudo nano /etc/systemd/system/gunicorn-api.service

# Change --workers 3 to --workers 1

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart gunicorn-api
```

## What I Need

Please run the diagnostic script above and send me:
1. The full output
2. Any specific error messages about imports or connections

This will tell us exactly why the workers are crashing!

