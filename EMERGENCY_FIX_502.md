# Emergency Fix: 502 Bad Gateway

## What Happened
The production server is returning `502 Bad Gateway` - this means the Flask application has stopped or crashed.

## Quick Fix (Production Server)

### Step 1: Check if Flask App is Running
```bash
# SSH into production
ssh your-user@api.ocpac.dcrc.ac.tz

# Check if gunicorn/Flask is running
ps aux | grep gunicorn
ps aux | grep python
ps aux | grep flask

# Check process on port 8000 (or whatever port Flask uses)
sudo lsof -i :8000
sudo netstat -tlnp | grep 8000
```

### Step 2: Check Application Logs
```bash
# Check application logs for errors
tail -100 /var/log/ocpac-api/error.log
# or
tail -100 /var/log/gunicorn/error.log
# or
journalctl -u ocpac-api -n 100 --no-pager

# Check nginx/Apache logs
tail -100 /var/log/nginx/error.log
```

### Step 3: Restart the Flask Application
```bash
# If running as systemd service
sudo systemctl restart ocpac-api
sudo systemctl status ocpac-api

# If running with gunicorn directly
pkill gunicorn
cd /path/to/ocpac-api
./start_flask_app.sh

# Or manually
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 wsgi:app
```

### Step 4: Check Nginx/Apache Configuration
```bash
# Test nginx config
sudo nginx -t

# Restart nginx if needed
sudo systemctl restart nginx

# Check if nginx is running
sudo systemctl status nginx
```

## Most Likely Causes

### 1. Flask App Crashed
**Symptom:** No gunicorn processes running
**Fix:**
```bash
cd /path/to/ocpac-api
./start_flask_app.sh
# or
sudo systemctl start ocpac-api
```

### 2. Import Error (Bad Code Changes)
**Symptom:** App starts then immediately crashes
**Check logs:**
```bash
tail -50 /var/log/ocpac-api/error.log
```

**Common errors:**
- `ImportError` or `ModuleNotFoundError`
- `SyntaxError`
- Database connection errors on startup

**Fix:** Check recent code changes, revert if needed

### 3. Port Already in Use
**Symptom:** "Address already in use" in logs
**Fix:**
```bash
# Find process using port 8000
sudo lsof -i :8000
# Kill it
sudo kill -9 PID_FROM_ABOVE
# Restart app
sudo systemctl restart ocpac-api
```

### 4. Out of Memory
**Symptom:** App killed without error message
**Check:**
```bash
free -h
dmesg | grep -i "out of memory"
```

**Fix:**
```bash
# Restart app
sudo systemctl restart ocpac-api

# Consider reducing workers
# Edit gunicorn config to use fewer workers
```

## Step-by-Step Recovery

### 1. Stop Everything
```bash
sudo systemctl stop ocpac-api
pkill -f gunicorn
pkill -f celery
```

### 2. Test Flask App Manually
```bash
cd /path/to/ocpac-api

# Activate virtual environment if using one
source venv/bin/activate

# Try to import the app
python3 -c "from app import app; print('OK')"
```

If this fails, you have a code/import issue. Check the error message.

### 3. Start App in Debug Mode
```bash
# Start on port 8000 in debug mode
python3 -c "from app import app; app.run(host='0.0.0.0', port=8000, debug=True)"
```

Watch for errors. If it starts successfully, Ctrl+C and continue to step 4.

### 4. Start Properly
```bash
# Start with gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 wsgi:app

# Or as service
sudo systemctl start ocpac-api
```

### 5. Test
```bash
# Test locally on server
curl http://localhost:8000/api/auth/login

# Test from outside
curl https://api.ocpac.dcrc.ac.tz/api/auth/login
```

## Check Recent Changes

The issue started after our database config changes. Let's verify the monitoring route is OK:

### Test Import
```bash
cd /path/to/ocpac-api
python3 << 'EOF'
try:
    from api.routes.monitoring_routes import monitoring_bp
    print("✅ Monitoring routes OK")
except Exception as e:
    print(f"❌ Error: {e}")
    
try:
    from app import app
    print("✅ App import OK")
except Exception as e:
    print(f"❌ Error: {e}")
EOF
```

## If Import Fails

There might be a syntax error or import issue in one of the files we modified. Check:

```bash
# Check syntax of modified files
python3 -m py_compile api/routes/monitoring_routes.py
python3 -m py_compile tasks_streamlined.py
python3 -m py_compile tasks.py
python3 -m py_compile tasks_migration.py
python3 -m py_compile tasks_local.py
python3 -m py_compile tasks_b2.py
```

## Emergency Rollback

If the app won't start due to recent changes:

```bash
cd /path/to/ocpac-api

# Revert recent commits
git log --oneline -5  # See recent commits
git revert HEAD  # Revert last commit
# or
git reset --hard HEAD~1  # Go back one commit (DANGEROUS)

# Restart
sudo systemctl restart ocpac-api
```

## Common 502 Error Patterns

### Pattern 1: Immediate 502
- App isn't running at all
- Wrong port in nginx config
- Firewall blocking internal connection

### Pattern 2: 502 After Working
- App crashed during request
- Database connection failed
- Import error in code

### Pattern 3: Intermittent 502
- App running but timing out
- Worker processes dying
- Memory issues

## Nginx Configuration Check

```bash
# Check nginx upstream configuration
cat /etc/nginx/sites-available/ocpac-api

# Should have something like:
# upstream app_server {
#     server 127.0.0.1:8000 fail_timeout=0;
# }
```

## Quick Diagnostic Commands

```bash
# Is Flask app responding?
curl http://127.0.0.1:8000/

# Is nginx running?
sudo systemctl status nginx

# Recent error logs
sudo journalctl -xe | tail -50

# System resources
top -bn1 | head -20
free -h
df -h
```

## What to Send Me

If still not working, run this and send output:

```bash
#!/bin/bash
echo "=== Flask App Status ==="
ps aux | grep -E "gunicorn|flask|python.*app" | grep -v grep

echo -e "\n=== Port 8000 Status ==="
sudo lsof -i :8000

echo -e "\n=== Recent App Logs ==="
tail -30 /var/log/ocpac-api/error.log 2>/dev/null || \
journalctl -u ocpac-api -n 30 --no-pager 2>/dev/null || \
echo "No logs found"

echo -e "\n=== Nginx Status ==="
sudo systemctl status nginx | head -20

echo -e "\n=== Recent Nginx Errors ==="
tail -10 /var/log/nginx/error.log

echo -e "\n=== Disk Space ==="
df -h | grep -E "/$|/var"

echo -e "\n=== Memory ==="
free -h

echo -e "\n=== Test Import ==="
cd /path/to/ocpac-api
python3 -c "from app import app; print('✅ App imports OK')" 2>&1
```

## Most Likely Fix

Based on the timing, the app probably crashed during startup due to an import or configuration error. 

**Try this first:**
```bash
# On production server
sudo systemctl stop ocpac-api
sudo systemctl start ocpac-api
sudo systemctl status ocpac-api

# Check if it's running
curl http://localhost:8000/
```

If that doesn't work, check the logs and send me the error message!

