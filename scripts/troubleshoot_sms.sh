#!/bin/bash
# Read-only checks; does not send SMS or print credentials/message content.
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
GUNICORN_SVC="${GUNICORN_SVC:-gunicorn-api}"
cd "$APP_ROOT"
python3 - <<'PY'
from pathlib import Path
values = {}
path = Path('.env')
if path.exists():
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.removeprefix('export ').split('=', 1)
            values[key.strip()] = value.strip().strip("\"'")
for key in ('MASTERCODES_SMS_SENDER_KEY', 'MASTERCODES_SMS_SENDER_SECRET'):
    print(key + ': ' + ('set in .env' if values.get(key) else 'missing in .env (check service environment)'))
PY
if command -v journalctl >/dev/null 2>&1; then
  journalctl -u "$GUNICORN_SVC" --no-pager -n 500 2>/dev/null |
    rg 'Mastercodes SMS response|SMS audit log write failed' || true
fi
