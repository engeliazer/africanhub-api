#!/usr/bin/env python3
"""
Send a test SMS via mShastra. Run from project root:
  python3 scripts/send_test_sms.py
  python3 scripts/send_test_sms.py 255717098911 "Your message"

Uses .env in project root for MSHASTRA_*. No venv required; needs 'requests'.
"""

import os
import re
import sys

# Project root (parent of scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# Load .env manually (no python-dotenv required)
def _load_env():
    path = os.path.join(ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v.startswith('"') and v.endswith('"') or v.startswith("'") and v.endswith("'"):
                v = v[1:-1]
            os.environ.setdefault(k, v)

_load_env()

DEFAULT_PHONE = "255717098911"
DEFAULT_MSG = "Test SMS from AfricanHub API. If you receive this, mShastra is working."


def main():
    phone = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PHONE
    message = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MSG

    print("=" * 50)
    print("Test SMS")
    print("=" * 50)
    print(f"Phone:  {phone}")
    print(f"Message: {message[:60]}{'...' if len(message) > 60 else ''}")
    print()

    user = os.getenv("MSHASTRA_USER", "AFRICANHUB")
    pwd = os.getenv("MSHASTRA_PWD", "")
    sender = os.getenv("MSHASTRA_SENDER", "AFRICANHUB")
    url = os.getenv("MSHASTRA_API_URL", "https://mshastra.com/sendsms_api_json.aspx")

    print("Config (from .env):")
    print(f"  MSHASTRA_USER:   {user}")
    print(f"  MSHASTRA_PWD:    {'(set)' if pwd else '(NOT SET)'}")
    print(f"  MSHASTRA_SENDER: {sender}")
    print(f"  API URL:         {url}")
    print()

    if not pwd:
        print("ERROR: MSHASTRA_PWD is not set. Add it to .env and try again.")
        sys.exit(1)

    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 9:
        normalized = "255" + digits[-9:]
    else:
        normalized = "255" + digits.lstrip("0") if not digits.startswith("255") else digits
    print(f"Normalized phone: {normalized}")
    print()

    payload = [
        {
            "user": user,
            "pwd": pwd,
            "number": normalized,
            "msg": message,
            "sender": sender,
            "language": "English",
        }
    ]

    print("Sending...")
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' not found. Run: pip install requests")
        print("Or use the project venv: venv/bin/python3 scripts/send_test_sms.py ...")
        sys.exit(1)

    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        print()
        print("API response:")
        print(f"  Status: {r.status_code}")
        print(f"  Body:   {r.text}")
        print("=" * 50)
        ok = r.status_code == 200
        if ok:
            print("Success. Check the phone for the SMS.")
        else:
            print("Failed. Check status/body above.")
        sys.exit(0 if ok else 1)
    except Exception as e:
        print()
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
