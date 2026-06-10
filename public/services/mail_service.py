"""
SMTP mail sending for batch campaigns (Zoho).
Credentials from MAIL_SMTP_* environment variables.
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NAME_PLACEHOLDER = "[NAME]"


def personalize_message(message_body: str, full_name: str) -> str:
    return message_body.replace(NAME_PLACEHOLDER, full_name or "")


def _smtp_config() -> dict:
    return {
        "host": os.getenv("MAIL_SMTP_HOST", "smtppro.zoho.com"),
        "port": int(os.getenv("MAIL_SMTP_PORT", "465")),
        "user": os.getenv("MAIL_SMTP_USER", ""),
        "password": os.getenv("MAIL_SMTP_PASS", ""),
        "use_ssl": os.getenv("MAIL_SMTP_USE_SSL", "true").lower() in ("1", "true", "yes"),
    }


def send_batch_email(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> Tuple[bool, Optional[str]]:
    """
    Send a single plain-text email via SMTP.

    Returns:
        (success, error_message)
    """
    cfg = _smtp_config()
    if not cfg["user"] or not cfg["password"]:
        return False, "Mail SMTP credentials not configured"

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        if cfg["use_ssl"] or cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as server:
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                server.starttls()
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP authentication failed: %s", e)
        return False, "SMTP authentication failed"
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to_email, e)
        return False, "SMTP send failed"
    except Exception as e:
        logger.exception("Unexpected error sending to %s", to_email)
        return False, str(e)
