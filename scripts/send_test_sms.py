#!/usr/bin/env python3
"""
Send a test SMS via mShastra. Run from project root:
  python scripts/send_test_sms.py
  # or
  python scripts/send_test_sms.py 255717098911 "Your message"

Uses .env in project root for MSHASTRA_*.
"""

import os
import re
import sys
import logging

# Project root (parent of scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from dotenv import load_dotenv
load_dotenv()

# Default test number and message
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

    # Normalize phone (same logic as sms_controller)
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 9:
        normalized = "255" + digits[-9:]
    else:
        normalized = "255" + digits if not digits.startswith("255") else digits
    print(f"Normalized phone: {normalized}")
    print()

    # Call SMSService
    from public.controllers.sms_controller import SMSService

    print("Sending...")
    result = SMSService.send_message(phone, message)
    print()
    print("Result:")
    print(f"  success: {result.get('success')}")
    print(f"  message: {result.get('message')}")
    if result.get("data"):
        print(f"  data:    {result['data']}")
    print("=" * 50)

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
