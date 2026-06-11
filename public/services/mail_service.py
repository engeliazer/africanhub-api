"""
Mail sending for batch campaigns.

Preferred on cloud VPS (DigitalOcean etc.): SendGrid API over HTTPS (port 443).
Fallback: Zoho SMTP via MAIL_SMTP_* variables.
"""

import logging
import os
import smtplib
import socket
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

NAME_PLACEHOLDER = "[NAME]"

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


def personalize_message(message_body: str, full_name: str) -> str:
    return message_body.replace(NAME_PLACEHOLDER, full_name or "")


def _mail_transport() -> str:
    """api | smtp | auto (default: api if key present, else smtp)."""
    mode = (os.getenv("MAIL_TRANSPORT") or "auto").strip().lower()
    if mode in ("api", "smtp"):
        return mode
    api_key = os.getenv("MAIL_SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY")
    return "api" if api_key and SENDGRID_AVAILABLE else "smtp"


def _default_from_email() -> str:
    return (
        os.getenv("MAIL_FROM")
        or os.getenv("MAIL_SMTP_USER")
        or ""
    ).strip()


def _sendgrid_api_key() -> str:
    return (os.getenv("MAIL_SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY") or "").strip()


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
        isinstance(err, OSError) and getattr(err, "errno", None) in (110, 60, 61)
    ):
        return (
            f"SMTP connection timed out to {host}:{port}. "
            "Outbound SMTP is blocked on this server — set MAIL_TRANSPORT=api and "
            "configure MAIL_SENDGRID_API_KEY (SendGrid uses HTTPS port 443)."
        )
    return str(err)


def _send_via_sendgrid(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> Tuple[bool, Optional[str]]:
    if not SENDGRID_AVAILABLE:
        return False, "SendGrid library not installed"
    api_key = _sendgrid_api_key()
    if not api_key:
        return False, "MAIL_SENDGRID_API_KEY not configured"
    send_from = _default_from_email() or from_email
    if from_email.lower() != send_from.lower():
        logger.warning(
            "from_email %s differs from MAIL_FROM %s; sending as %s",
            from_email,
            send_from,
            send_from,
        )
    try:
        mail = Mail(
            from_email=(send_from, "African Hub"),
            to_emails=[to_email],
            subject=subject,
            plain_text_content=body,
        )
        sg = SendGridAPIClient(api_key)
        response = sg.send(mail)
        if response.status_code in (200, 201, 202):
            return True, None
        error_body = response.body.decode("utf-8") if response.body else "No error body"
        return False, f"SendGrid API error {response.status_code}: {error_body}"
    except Exception as e:
        status = getattr(e, "status_code", None)
        body = getattr(e, "body", None)
        if body and hasattr(body, "decode"):
            body = body.decode("utf-8")
        if status == 401:
            msg = (
                "SendGrid API key rejected (401 Unauthorized). "
                "Check SENDGRID_API_KEY in the server .env, restart Gunicorn, "
                "and ensure the key has Mail Send permission."
            )
            if body:
                msg = f"{msg} Response: {body}"
            logger.error("SendGrid 401 for %s: %s", to_email, body or e)
            return False, msg
        logger.exception("SendGrid error sending to %s", to_email)
        if status and body:
            return False, f"SendGrid API error {status}: {body}"
        return False, f"SendGrid send failed: {e}"


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


def _send_via_smtp(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> Tuple[bool, Optional[str]]:
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


def send_batch_email(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> Tuple[bool, Optional[str]]:
    """
    Send a single plain-text email.

    Uses SendGrid API when MAIL_TRANSPORT=api (or auto + API key set),
    otherwise SMTP.
    """
    transport = _mail_transport()
    if transport == "api":
        return _send_via_sendgrid(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
        )
    return _send_via_smtp(
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        body=body,
    )
