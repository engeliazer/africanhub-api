"""
Mail sending for batch campaigns.

Preferred: Amazon SES API over HTTPS (port 443), MAIL_TRANSPORT=ses.
Fallback: SendGrid API, then Zoho SMTP via MAIL_SMTP_* variables.
"""

import base64
import logging
import os
import smtplib
import socket
from email import encoders
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from dotenv import load_dotenv

from public.services.mail_html_template import render_batch_email_html

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

NAME_PLACEHOLDER = "[NAME]"

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Attachment,
        Disposition,
        FileContent,
        FileName,
        FileType,
        Mail,
    )
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


def personalize_message(message_body: str, full_name: str) -> str:
    return message_body.replace(NAME_PLACEHOLDER, full_name or "")


def _html_enabled() -> bool:
    # Plain text by default. HTML wrappers (logo, styled layout, footer links)
    # make inbox providers classify batch mail as promotions.
    return os.getenv("MAIL_HTML_ENABLED", "false").lower() in ("1", "true", "yes")


def _build_html_body(
    plain_body: str,
    subject: str,
    *,
    use_html: Optional[bool] = None,
) -> Optional[str]:
    enabled = _html_enabled() if use_html is None else use_html
    if not enabled:
        return None
    try:
        return render_batch_email_html(message_body=plain_body, subject=subject)
    except Exception:
        logger.exception("Failed to render HTML email template")
        return None


def _mail_transport() -> str:
    """ses | api | smtp | auto (ses when AWS keys and region are set, else SendGrid, else SMTP)."""
    mode = (os.getenv("MAIL_TRANSPORT") or "auto").strip().lower()
    if mode in ("api", "smtp", "ses"):
        return mode
    if _ses_ready():
        return "ses"
    api_key = os.getenv("MAIL_SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY")
    return "api" if api_key and SENDGRID_AVAILABLE else "smtp"


def _ses_credentials() -> Tuple[str, str, str]:
    key = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    secret = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    region = (os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "").strip()
    if not key or not secret:
        raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required for SES")
    if not region:
        raise ValueError("AWS_DEFAULT_REGION is required for SES")
    return key, secret, region


def _ses_ready() -> bool:
    return bool(
        (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
        and (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
        and (os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "").strip()
    )


def _default_from_email() -> str:
    return (
        os.getenv("MAIL_FROM")
        or os.getenv("MAIL_SMTP_USER")
        or ""
    ).strip()


def _from_display_name() -> str:
    return (os.getenv("MAIL_FROM_NAME") or "African Hub").strip() or "African Hub"


def _resolve_sender_email(from_email: str) -> str:
    """Use batch source_email when set; otherwise fall back to MAIL_FROM."""
    explicit = (from_email or "").strip()
    if explicit:
        return explicit
    fallback = _default_from_email()
    if not fallback:
        raise ValueError("No sender email: set source_email on the batch or MAIL_FROM in .env")
    return fallback


def _reply_to_email() -> str:
    """Inbox that receives replies (independent of batch source_email / From header)."""
    reply_to = (os.getenv("MAIL_REPLY_TO") or _default_from_email() or "").strip()
    if not reply_to:
        raise ValueError("No reply-to email: set MAIL_REPLY_TO or MAIL_FROM in .env")
    return reply_to


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


def _load_attachment(
    attachment_path: Optional[str],
    attachment_filename: Optional[str],
) -> Optional[Tuple[bytes, str]]:
    if not attachment_path:
        return None
    path = Path(attachment_path)
    if not path.is_file():
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")
    filename = attachment_filename or path.name
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return path.read_bytes(), filename


def _load_attachments(
    attachment_path: Optional[str],
    attachment_filename: Optional[str],
    extra_attachments: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
) -> List[Tuple[bytes, str]]:
    pairs = [(attachment_path, attachment_filename), *(extra_attachments or [])]
    loaded = [_load_attachment(path, name) for path, name in pairs]
    return [item for item in loaded if item]


def _send_via_sendgrid(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    attachment_filename: Optional[str] = None,
    extra_attachments: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
    use_html: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    if not SENDGRID_AVAILABLE:
        return False, "SendGrid library not installed"
    api_key = _sendgrid_api_key()
    if not api_key:
        return False, "MAIL_SENDGRID_API_KEY not configured"
    try:
        send_from = _resolve_sender_email(from_email)
        reply_to = _reply_to_email()
    except ValueError as e:
        return False, str(e)
    html_body = _build_html_body(body, subject, use_html=use_html)
    try:
        mail_kwargs = {
            "from_email": (send_from, _from_display_name()),
            "to_emails": [to_email],
            "subject": subject,
            "plain_text_content": body,
        }
        if html_body:
            mail_kwargs["html_content"] = html_body
        mail = Mail(**mail_kwargs)
        mail.reply_to = (reply_to, _from_display_name())
        for data, filename in _load_attachments(
            attachment_path, attachment_filename, extra_attachments
        ):
            encoded = base64.b64encode(data).decode("utf-8")
            mail.add_attachment(
                Attachment(
                    FileContent(encoded),
                    FileName(filename),
                    FileType("application/pdf"),
                    Disposition("attachment"),
                )
            )
        sg = SendGridAPIClient(api_key)
        response = sg.send(mail)
        if response.status_code in (200, 201, 202):
            return True, None
        error_body = response.body.decode("utf-8") if response.body else "No error body"
        return False, f"SendGrid API error {response.status_code}: {error_body}"
    except FileNotFoundError as e:
        return False, str(e)
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


def _build_body_part(
    plain_body: str,
    subject: str,
    *,
    use_html: Optional[bool] = None,
):
    """Plain text, or multipart/alternative when the HTML wrapper is enabled."""
    html_body = _build_html_body(plain_body, subject, use_html=use_html)
    if not html_body:
        return MIMEText(plain_body, "plain", "utf-8")
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(plain_body, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    return alternative


def _build_smtp_message(
    *,
    send_from: str,
    reply_to: str,
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    attachment_filename: Optional[str] = None,
    extra_attachments: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
    use_html: Optional[bool] = None,
):
    attachments = _load_attachments(attachment_path, attachment_filename, extra_attachments)
    body_part = _build_body_part(body, subject, use_html=use_html)
    if attachments:
        msg = MIMEMultipart("mixed")
        msg.attach(body_part)
        for data, filename in attachments:
            part = MIMEBase("application", "pdf")
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)
    else:
        msg = body_part

    msg["From"] = send_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = reply_to
    return msg


def _send_smtp_message(cfg: dict, msg: Message) -> None:
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
    attachment_path: Optional[str] = None,
    attachment_filename: Optional[str] = None,
    extra_attachments: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
    use_html: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    cfg = _smtp_config()
    if not cfg["user"] or not cfg["password"]:
        return False, "Mail SMTP credentials not configured"

    try:
        send_from = _resolve_sender_email(from_email)
        reply_to = _reply_to_email()
    except ValueError as e:
        return False, str(e)

    if send_from.lower() != cfg["user"].lower():
        logger.info(
            "SMTP login as %s, From: %s, Reply-To: %s",
            cfg["user"],
            send_from,
            reply_to,
        )

    try:
        msg = _build_smtp_message(
            send_from=send_from,
            reply_to=reply_to,
            to_email=to_email,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
            attachment_filename=attachment_filename,
            extra_attachments=extra_attachments,
            use_html=use_html,
        )
        _send_smtp_message(cfg, msg)
        return True, None
    except FileNotFoundError as e:
        return False, str(e)
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


def _send_via_ses(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    attachment_filename: Optional[str] = None,
    extra_attachments: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
    use_html: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        return False, "boto3 is not installed"

    try:
        send_from = _resolve_sender_email(from_email)
        reply_to = _reply_to_email()
        key, secret, region = _ses_credentials()
    except ValueError as e:
        return False, str(e)

    try:
        msg = _build_smtp_message(
            send_from=send_from,
            reply_to=reply_to,
            to_email=to_email,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
            attachment_filename=attachment_filename,
            extra_attachments=extra_attachments,
            use_html=use_html,
        )
        msg.replace_header("From", formataddr((_from_display_name(), send_from)))
        client = boto3.client(
            "ses",
            region_name=region,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
        )
        client.send_raw_email(
            Source=send_from,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_bytes()},
        )
        return True, None
    except FileNotFoundError as e:
        return False, str(e)
    except ClientError as e:
        err = e.response.get("Error", {}) if getattr(e, "response", None) else {}
        code = err.get("Code", "ClientError")
        message = err.get("Message", str(e))
        logger.error("SES error sending to %s: %s %s", to_email, code, message)
        return False, f"SES {code}: {message}"
    except BotoCoreError as e:
        logger.exception("SES connection error sending to %s", to_email)
        return False, f"SES send failed: {e}"
    except Exception as e:
        logger.exception("Unexpected SES error sending to %s", to_email)
        return False, str(e)


def send_batch_email(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    attachment_filename: Optional[str] = None,
    extra_attachments: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
    use_html: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Send email with optional PDF attachment, plus any extra_attachments
    given as (path, filename) pairs.

    Body is sent as plain text. Set MAIL_HTML_ENABLED=true to also attach the
    branded HTML wrapper (that layout is what inboxes tend to file as promotions).

    Uses Amazon SES when MAIL_TRANSPORT=ses (or auto when AWS keys and region are set).
    SendGrid is used when MAIL_TRANSPORT=api. Otherwise SMTP.
    """
    transport = _mail_transport()
    if transport == "ses":
        return _send_via_ses(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
            attachment_filename=attachment_filename,
            extra_attachments=extra_attachments,
            use_html=use_html,
        )
    if transport == "api":
        return _send_via_sendgrid(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
            attachment_filename=attachment_filename,
            extra_attachments=extra_attachments,
            use_html=use_html,
        )
    return _send_via_smtp(
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        body=body,
        attachment_path=attachment_path,
        attachment_filename=attachment_filename,
        extra_attachments=extra_attachments,
        use_html=use_html,
    )
