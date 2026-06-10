"""
SMTP mail sending for batch campaigns (Zoho).
Credentials from MAIL_SMTP_* environment variables.
"""

import logging
import os
import smtplib
import socket
from email.mime.text import MIMEText
from typing import Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NAME_PLACEHOLDER = "[NAME]"


def personalize_message(message_body: str, full_name: str) -> str:
    return message_body.replace(NAME_PLACEHOLDER, full_name or "")


def _smtp_config() -> dict:
    port = int(os.getenv("MAIL_SMTP_PORT", "587"))
    use_ssl = os.getenv("MAIL_SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
    if port == 465:
        use_ssl = True
    return {
        "host": os.getenv("MAIL_SMTP_HOST", "smtppro.zoho.com"),
        "port": port,
        "user": os.getenv("MAIL_SMTP_USER", ""),
        "password": os.getenv("MAIL_SMTP_PASS", ""),
        "use_ssl": use_ssl,
        "timeout": int(os.getenv("MAIL_SMTP_TIMEOUT", "30")),
    }


def _connection_error_message(host: str, port: int, err: Exception) -> str:
    if isinstance(err, (TimeoutError, socket.timeout)) or (
        isinstance(err, OSError) and err.errno in (110, 60, 61)
    ):
        return (
            f"SMTP connection timed out to {host}:{port}. "
            "Your server may block outbound SMTP — try MAIL_SMTP_PORT=587 and "
            "MAIL_SMTP_USE_SSL=false, or open the port in the cloud firewall."
        )
    return str(err)


def _send_smtp_message(cfg: dict, msg: MIMEText) -> None:
    if cfg["use_ssl"]:
        server = smtplib.SMTP_SSL(
            cfg["host"], cfg["port"], timeout=cfg["timeout"]
        )
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=cfg["timeout"])
    try:
        if not cfg["use_ssl"]:
            server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


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

    send_from = cfg["user"]
    if from_email.lower() != send_from.lower():
        logger.warning(
            "from_email %s does not match MAIL_SMTP_USER %s; sending as %s",
            from_email,
            send_from,
            send_from,
        )

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = send_from
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        _send_smtp_message(cfg, msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed for %s", cfg["user"])
        return False, "SMTP authentication failed"
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to_email, e)
        return False, f"SMTP send failed: {e}"
    except (OSError, TimeoutError, socket.timeout) as e:
        logger.error("SMTP connection error to %s:%s: %s", cfg["host"], cfg["port"], e)
        return False, _connection_error_message(cfg["host"], cfg["port"], e)
    except Exception as e:
        logger.exception("Unexpected error sending to %s", to_email)
        return False, str(e)
