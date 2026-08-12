#!/bin/bash
# 502 Bad Gateway diagnostics for africanhub-api
# Run on the server:
#   cd /var/www/africanhub-api.africanhub.ac.tz
#   bash scripts/troubleshoot_502.sh

APP_ROOT="${APP_ROOT:-/var/www/africanhub-api.africanhub.ac.tz}"
cd "$APP_ROOT" || exit 1

echo "=========================================="
echo "502 troubleshooting — $APP_ROOT"
echo "=========================================="

echo ""
echo "--- 1. Systemd services (gunicorn / api) ---"
for u in africanhub-api gunicorn-api gunicorn africanhub; do
  if systemctl list-unit-files "$u.service" 2>/dev/null | grep -q "$u.service"; then
    echo "Unit: $u"
    systemctl is-active "$u" 2>/dev/null || true
    systemctl status "$u" --no-pager -l 2>/dev/null | head -25 || true
    echo ""
  fi
done

echo "--- 2. Gunicorn / Python processes ---"
ps aux | grep -E "gunicorn|wsgi:app|python.*app" | grep -v grep || echo "(no matching processes)"

echo ""
echo "--- 3. Listening ports (8000 / unix socket) ---"
ss -tlnp 2>/dev/null | grep -E ':8000|:80|:443' || netstat -tlnp 2>/dev/null | grep -E ':8000|:80|:443' || true
for sock in gunicorn.sock africanhub-api.sock; do
  find /var/www -name "$sock" 2>/dev/null
done

echo ""
echo "--- 4. Recent journal logs (africanhub-api) ---"
sudo journalctl -u africanhub-api -n 60 --no-pager 2>/dev/null || echo "(no africanhub-api journal)"

echo ""
echo "--- 5. Recent journal logs (gunicorn-api) ---"
sudo journalctl -u gunicorn-api -n 60 --no-pager 2>/dev/null || echo "(no gunicorn-api journal)"

echo ""
echo "--- 6. Nginx errors ---"
sudo tail -20 /var/log/nginx/error.log 2>/dev/null || echo "(no nginx error log access)"

echo ""
echo "--- 7. Python import test (wsgi:app) ---"
if [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "WARNING: venv/bin/activate not found"
fi

python3 <<'PY'
import traceback
import sys

print("Python:", sys.executable)

for label, stmt in [
    ("database.base", "from database.base import Base"),
    ("app", "from app import app"),
    ("wsgi", "from wsgi import app"),
]:
    try:
        exec(stmt)
        print(f"OK  import {label}")
    except Exception as exc:
        print(f"FAIL import {label}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)

print(f"OK  routes registered: {len(list(app.url_map.iter_rules()))}")
PY
IMPORT_RC=$?

echo ""
echo "--- 8. Certificate PDF deps (optional) ---"
python3 scripts/check_certificate_pdf_deps.py 2>&1 || true

echo ""
echo "--- 9. Local curl (bypass nginx) ---"
curl -s -o /dev/null -w "localhost:8000/api/events -> HTTP %{http_code}\n" --max-time 5 http://127.0.0.1:8000/api/events 2>/dev/null \
  || echo "localhost:8000 not responding"

echo ""
if [ "$IMPORT_RC" -ne 0 ]; then
  echo "RESULT: Import failed — fix the traceback above, then: sudo systemctl restart africanhub-api"
  exit 1
fi
echo "RESULT: Imports OK. If still 502, check nginx upstream vs gunicorn bind (port/socket)."
