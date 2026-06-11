#!/usr/bin/env python3
"""Quick SendGrid check for mail batch config. Run on the production server."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

api_key = (os.getenv("MAIL_SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY") or "").strip()
mail_from = (os.getenv("MAIL_FROM") or os.getenv("MAIL_SMTP_USER") or "").strip()
transport = (os.getenv("MAIL_TRANSPORT") or "auto").strip()

print(f"MAIL_TRANSPORT: {transport}")
print(f"MAIL_FROM: {mail_from or '(missing)'}")
print(f"SENDGRID_API_KEY: {'set' if api_key else 'MISSING'} (length={len(api_key)})")
if api_key and not api_key.startswith("SG."):
    print("WARNING: API key should start with SG.")

if not api_key:
    sys.exit(1)

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError as e:
    print(f"sendgrid not installed: {e}")
    sys.exit(1)

to_email = sys.argv[1] if len(sys.argv) > 1 else "engeliazer@gmail.com"
if not mail_from:
    print("Set MAIL_FROM=trainings@africanhub.ac.tz in .env")
    sys.exit(1)

mail = Mail(
    from_email=(mail_from, "African Hub"),
    to_emails=[to_email],
    subject="SendGrid batch test",
    plain_text_content="If you receive this, SendGrid API is working.",
)
try:
    response = SendGridAPIClient(api_key).send(mail)
    print(f"OK status={response.status_code}")
except Exception as e:
    print(f"FAILED: {e}")
    if getattr(e, "body", None):
        body = e.body.decode("utf-8") if hasattr(e.body, "decode") else e.body
        print(f"Body: {body}")
    sys.exit(1)
