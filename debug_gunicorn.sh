#!/bin/bash
# Debug Gunicorn startup issues

echo "=== 1. Check Full Gunicorn Logs ==="
sudo journalctl -u gunicorn-api -n 100 --no-pager | tail -50

echo ""
echo "=== 2. Test Python Import ==="
cd /var/www/api.online.dcrc.ac.tz
source venv/bin/activate
python3 -c "
try:
    from sendgrid import SendGridAPIClient
    print('✅ SendGrid import works')
except Exception as e:
    print(f'❌ SendGrid import failed: {e}')

try:
    from public.controllers.contact_controller import contact_bp
    print('✅ Contact controller import works')
except Exception as e:
    print(f'❌ Contact controller import failed: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "=== 3. Test Flask App Load ==="
python3 -c "
import sys
sys.path.insert(0, '/var/www/api.online.dcrc.ac.tz')
try:
    from app import app
    print('✅ Flask app loaded successfully')
    print(f'✅ App has {len(app.url_map._rules)} routes')
except Exception as e:
    print(f'❌ Flask app failed to load: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "=== 4. Check Environment Variables ==="
cd /var/www/api.online.dcrc.ac.tz
source venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
sg_key = os.getenv('SENDGRID_API_KEY')
print(f'SENDGRID_API_KEY: {\"configured\" if sg_key else \"missing\"} (length: {len(sg_key) if sg_key else 0})')
print(f'EMAIL_FROM: {os.getenv(\"EMAIL_FROM\", \"missing\")}')
print(f'EMAIL_TO: {os.getenv(\"EMAIL_TO\", \"missing\")}')
"

echo ""
echo "=== 5. Restart Gunicorn and Watch Logs ==="
echo "Restarting Gunicorn..."
sudo systemctl restart gunicorn-api
sleep 3
echo "Recent logs:"
sudo journalctl -u gunicorn-api -n 20 --no-pager

