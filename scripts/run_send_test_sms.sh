#!/bin/bash
# Run send_test_sms.py with project venv if available (has requests, etc.)
cd "$(dirname "$0")/.."
if [ -f venv/bin/python3 ]; then
  exec venv/bin/python3 scripts/send_test_sms.py "$@"
elif [ -f .venv/bin/python3 ]; then
  exec .venv/bin/python3 scripts/send_test_sms.py "$@"
else
  exec python3 scripts/send_test_sms.py "$@"
fi
