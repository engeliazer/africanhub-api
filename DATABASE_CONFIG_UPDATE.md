# Database Configuration Update for Celery Workers

## Issue
Celery workers were getting "Database connection failed" errors because they had incorrect/outdated database credentials.

## Root Cause
Each Celery task file (`tasks_streamlined.py`, `tasks.py`, `tasks_migration.py`, etc.) had hardcoded database configurations that were:
- Using wrong credentials (root user with no password)
- Not synchronized with the actual database configuration

## Solution Applied
Updated all Celery task files with correct database credentials from `.env`:

**Correct Configuration:**
```python
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'ocpac',
    'password': 'oCpAc@2025',
    'database': 'ocpac',
    'charset': 'utf8mb4',
    'autocommit': True,
    'port': 3306
}
```

## Files Updated

### Primary Task Files:
1. ✅ `tasks_streamlined.py` - Main HLS video processing tasks
2. ✅ `tasks.py` - Legacy video processing tasks
3. ✅ `tasks_migration.py` - B2 storage migration tasks
4. ✅ `tasks_local.py` - Local storage tasks
5. ✅ `tasks_b2.py` - B2 storage tasks

### Monitoring Files:
6. ✅ `api/routes/monitoring_routes.py` - Monitoring API endpoints

## Why Hardcoded Credentials?

We intentionally used hardcoded credentials instead of loading from `.env` because:

1. **Previous timing issues** - Loading environment variables in Celery workers caused timeout problems
2. **Reliability** - Celery workers need immediate access to database without environment loading delays
3. **Consistency** - All workers use the same configuration without dependency on environment loading order

## Production Deployment

When deploying to production with different database credentials:

1. **Update credentials in ALL task files** listed above
2. **Restart Celery workers** after changes:
   ```bash
   # Kill existing workers
   pkill -f celery
   
   # Start new workers
   celery -A celery_config.celery worker --loglevel=info --concurrency=2 --pool=prefork
   ```
3. **Verify connection** - Check worker logs for successful database connections

## Testing After Update

### 1. Test Worker Startup
```bash
celery -A celery_config.celery worker --loglevel=info
```

Look for log line:
```
Database config - Host: 127.0.0.1, User: ocpac, Database: ocpac
```

### 2. Test Database Connection
```bash
mysql -u ocpac -p'oCpAc@2025' -h 127.0.0.1 ocpac -e "SELECT COUNT(*) FROM subtopic_materials;"
```

### 3. Test Video Upload
Upload a video through the API and monitor:
```bash
# Watch worker logs
tail -f /var/log/celery/ocpac-worker.log

# Check material status
mysql -u ocpac -p'oCpAc@2025' ocpac -e "SELECT id, name, processing_status FROM subtopic_materials ORDER BY id DESC LIMIT 5;"
```

## Production Server Credentials

For **production deployment**, you'll need to update the credentials in all task files to match your production database:

```python
DB_CONFIG = {
    'host': 'YOUR_PRODUCTION_HOST',      # e.g., 'localhost' or '127.0.0.1'
    'user': 'YOUR_PRODUCTION_USER',       # e.g., 'ocpac'
    'password': 'YOUR_PRODUCTION_PASSWORD',
    'database': 'YOUR_PRODUCTION_DB',     # e.g., 'ocpac'
    'charset': 'utf8mb4',
    'autocommit': True,
    'port': 3306
}
```

### Production Update Script

Create a script to update all files at once:

```bash
#!/bin/bash
# update_db_credentials.sh

OLD_HOST="127.0.0.1"
NEW_HOST="your_production_host"

OLD_USER="ocpac"
NEW_USER="your_production_user"

OLD_PASS="oCpAc@2025"
NEW_PASS="your_production_password"

# Update all task files
for file in tasks_streamlined.py tasks.py tasks_migration.py tasks_local.py tasks_b2.py api/routes/monitoring_routes.py; do
    echo "Updating $file..."
    sed -i "s/'host': '$OLD_HOST'/'host': '$NEW_HOST'/g" $file
    sed -i "s/'user': '$OLD_USER'/'user': '$NEW_USER'/g" $file
    sed -i "s/'password': '$OLD_PASS'/'password': '$NEW_PASS'/g" $file
done

echo "Done! Don't forget to restart Celery workers."
```

## Troubleshooting

### Workers still getting connection errors

1. **Check credentials are correct:**
   ```bash
   grep -A 6 "DB_CONFIG = {" tasks_streamlined.py
   ```

2. **Test database connection manually:**
   ```bash
   mysql -u ocpac -p'oCpAc@2025' -h 127.0.0.1 ocpac -e "SHOW TABLES;"
   ```

3. **Restart workers:**
   ```bash
   pkill -f celery
   celery -A celery_config.celery worker --loglevel=info --concurrency=2
   ```

### Credentials work locally but not on production

1. Check production database host/port are accessible
2. Verify firewall rules allow MySQL connections
3. Confirm user has proper permissions:
   ```sql
   SHOW GRANTS FOR 'ocpac'@'localhost';
   SHOW GRANTS FOR 'ocpac'@'%';
   ```

### Permission Issues

If worker gets "Access denied" errors:
```sql
-- Grant all permissions
GRANT ALL PRIVILEGES ON ocpac.* TO 'ocpac'@'localhost' IDENTIFIED BY 'oCpAc@2025';
GRANT ALL PRIVILEGES ON ocpac.* TO 'ocpac'@'%' IDENTIFIED BY 'oCpAc@2025';
FLUSH PRIVILEGES;
```

## Related Configuration

### Flask App Database Config
The Flask application uses environment variables from `.env`:
```
DB_USER=ocpac
DB_PASSWORD=oCpAc%402025
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=ocpac
```

Note: Password is URL-encoded in `.env` (`%40` = `@`)

### Celery Workers
Use hardcoded credentials as documented above to avoid environment loading issues.

## Summary

- ✅ All Celery task files now have correct database credentials
- ✅ Credentials are hardcoded to avoid environment variable loading issues
- ✅ Workers should now connect successfully to the database
- ⚠️  Remember to update credentials when deploying to production
- ⚠️  Always restart Celery workers after credential changes

