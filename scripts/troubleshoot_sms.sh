#!/bin/bash
# SMS troubleshooting for africanhub-api deployment
# Run on server:
#   cd /var/www/africanhub-api.africanhub.ac.tz
#   bash scripts/troubleshoot_sms.sh

set -e
APP_ROOT="${APP_ROOT:-/var/www/africanhub-api.africanhub.ac.tz}"
GUNICORN_SVC="${GUNICORN_SVC:-gunicorn-api}"
cd "$APP_ROOT"

echo "=========================================="
echo "SMS / mShastra troubleshooting"
echo "App root: $APP_ROOT"
echo "=========================================="

echo ""
echo "--- 1. Env vars (MSHASTRA_*) ---"
if [ -f .env ]; then
  grep -E '^MSHASTRA_|^#.*MSHASTRA' .env 2>/dev/null || echo "(none found)"
else
  echo ".env not found"
fi
# Also check systemd / gunicorn env
for u in gunicorn-api gunicorn africanhub-api africanhub; do
  systemctl is-active --quiet "$u" 2>/dev/null && { echo "Active unit: $u"; systemctl show "$u" 2>/dev/null | grep -i mshastra || true; break; }
done

echo ""
echo "--- 2. Where do logs go? ---"
echo "Gunicorn / app logs:"
for f in logs/*.log log/*.log /var/log/gunicorn/*.log /var/log/africanhub* 2>/dev/null; do
  [ -e "$f" ] && echo "  $f"
done
ls -la logs/ 2>/dev/null || true
ls -la log/ 2>/dev/null || true

echo ""
echo "--- 3. Recent SMS-related log lines ---"
for log in logs/*.log log/*.log /var/log/gunicorn/*.log; do
  [ -f "$log" ] || continue
  echo ">>> $log"
  grep -E "SMS API|SMS send_message|MSHASTRA|send_message" "$log" 2>/dev/null | tail -50 || true
done
# Journal if gunicorn runs under systemd
if command -v journalctl &>/dev/null; then
  echo ">>> journalctl ($GUNICORN_SVC)"
  journalctl -u "$GUNICORN_SVC" --no-pager -n 300 2>/dev/null | grep -E "SMS API|SMS send|MSHASTRA|send_message" || true
fi

echo ""
echo "--- 4. 'SMS API says:' (raw API response) ---"
for log in logs/*.log log/*.log /var/log/gunicorn/*.log; do
  [ -f "$log" ] || continue
  grep "SMS API says:" "$log" 2>/dev/null | tail -20 || true
done
journalctl -u "$GUNICORN_SVC" --no-pager -n 500 2>/dev/null | grep "SMS API says:" || true

echo ""
echo "--- 5. Python app / gunicorn process ---"
ps aux | grep -E "gunicorn|flask|python.*app" | grep -v grep || echo "(no matching processes)"

echo ""
echo "--- 6. Quick curl test (mShastra API) ---"
# Don't send real SMS; just check connectivity
URL="${MSHASTRA_API_URL:-https://mshastra.com/sendsms_api_json.aspx}"
echo "URL: $URL"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '[{"user":"x","pwd":"y","number":"255700000000","msg":"test","sender":"x","language":"English"}]' 2>/dev/null || echo "curl failed"

echo ""
echo "=========================================="
echo "Done. Share 'SMS API says:' lines and any errors above."
echo "=========================================="
