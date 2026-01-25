"""
SMS service using mShastra API.

Provider: mShastra (https://mshastra.com)
- JSON API: POST to sendsms_api_json.aspx
- Optional URL APIs: sendurl.aspx (single), sendurlcomma.aspx (multiple)

Env vars (recommended):
  MSHASTRA_USER     – Profile ID (e.g. AFRICANHUB)
  MSHASTRA_PWD      – Password
  MSHASTRA_SENDER   – Sender ID (e.g. AFRICANHUB)

All SMS are logged to sms_logs for audit and reconciliation.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import json
import re
import os
import logging
import requests
from datetime import datetime, time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

sms_bp = Blueprint('sms', __name__)
logger = logging.getLogger(__name__)

# Lazy imports for DB (avoid circular imports / import at module load)
def _get_session_and_model():
    from database.db_connector import SessionLocal
    from applications.models.models import SmsLog
    return SessionLocal, SmsLog


def _log_sms(
    *,
    sender_id: str,
    recipient: str,
    message: str,
    message_length: int,
    process_name: str,
    status: str,
    provider: str = "mshastra",
    external_id: Optional[str] = None,
    api_response_raw: Optional[str] = None,
    error_message: Optional[str] = None,
    created_by: Optional[int] = None,
) -> None:
    """Write audit log for an SMS. Uses a dedicated session; swallows errors so logging never breaks SMS flow."""
    try:
        SessionLocal, SmsLog = _get_session_and_model()
        session = SessionLocal()
        try:
            row = SmsLog(
                sender_id=sender_id,
                recipient=recipient,
                message=message,
                message_length=message_length,
                process_name=process_name,
                status=status,
                provider=provider,
                external_id=external_id,
                api_response_raw=api_response_raw,
                error_message=error_message,
                created_by=created_by,
            )
            session.add(row)
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.warning("SMS audit log write failed: %s", e)

# mShastra JSON API endpoint
MSHASTRA_JSON_URL = os.getenv('MSHASTRA_API_URL', 'https://mshastra.com/sendsms_api_json.aspx')
DEFAULT_COUNTRY_CODE = '255'
DEFAULT_LANGUAGE = 'English'


def _normalize_phone(phone: str, use_last_nine: bool = True) -> str:
    """
    Normalize phone for mShastra (Tanzania).
    - use_last_nine=True: strip to digits, take last 9, prefix 255 (e.g. 0712001002 -> 255712001002).
    - use_last_nine=False: strip to digits only; if missing 255 prefix, add it.
    """
    if not phone or not isinstance(phone, str):
        return ''
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return ''

    if use_last_nine:
        last_nine = digits[-9:] if len(digits) >= 9 else digits
        return DEFAULT_COUNTRY_CODE + last_nine

    if not digits.startswith(DEFAULT_COUNTRY_CODE):
        digits = DEFAULT_COUNTRY_CODE + digits.lstrip('0')
    return digits


def _config() -> Dict[str, str]:
    cfg = {
        'user': os.getenv('MSHASTRA_USER', 'AFRICANHUB'),
        'pwd': os.getenv('MSHASTRA_PWD', ''),
        'sender': os.getenv('MSHASTRA_SENDER', 'AFRICANHUB'),
    }
    if not cfg['pwd']:
        logger.warning("MSHASTRA_PWD is not set; SMS API may reject requests")
    return cfg


def _send_json_payload(payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    """POST JSON array to mShastra JSON API. payload = list of {user, pwd, number, msg, sender, language}."""
    # Log request with masked password
    mask = [{**p, 'pwd': '***'} for p in payload]
    logger.info(
        "SMS API request: url=%s payload=%s",
        MSHASTRA_JSON_URL,
        mask,
        extra={'sms_payload_masked': mask},
    )
    try:
        resp = requests.post(
            MSHASTRA_JSON_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        logger.info(
            "SMS API response: status=%s body=%s",
            resp.status_code,
            resp.text,
            extra={'sms_status': resp.status_code, 'sms_response': resp.text},
        )
        # Grep-friendly line: "SMS API says: ..."
        logger.info("SMS API says: [status=%s] %s", resp.status_code, resp.text)
        return {'success': resp.status_code == 200, 'status_code': resp.status_code, 'text': resp.text}
    except Exception as e:
        logger.exception("SMS API error: %s", e)
        return {'success': False, 'status_code': None, 'text': str(e)}


def _parse_external_id(response_text: str) -> Optional[str]:
    """Extract msg_id from mShastra JSON response [{"msg_id":"...", ...}]."""
    try:
        arr = json.loads(response_text)
        if arr and isinstance(arr[0], dict) and arr[0].get("msg_id"):
            return str(arr[0]["msg_id"])
    except Exception:
        pass
    return None


class SMSService:
    @staticmethod
    def send_message(
        phone: str,
        message: str,
        sender: Optional[str] = None,
        use_last_nine: bool = True,
        process_name: str = "unknown",
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a single SMS via mShastra JSON API. Always logged to sms_logs.

        Args:
            phone: Recipient number (e.g. 0712001002 or 255712001002).
            message: SMS text.
            sender: Sender ID override; if None, uses MSHASTRA_SENDER env.
            use_last_nine: If True, use last 9 digits + 255; else use full normalized number.
            process_name: Process/campaign name for audit (e.g. registration, password_reset).
            created_by: Optional user id for audit.

        Returns:
            {'success': bool, 'data': {...} | None, 'message': str}
        """
        cfg = _config()
        sender_id = sender or cfg["sender"]
        msg_len = len(message or "")
        normalized = _normalize_phone(phone, use_last_nine=use_last_nine)

        logger.info(
            "SMS send_message: phone=%r normalized=%r sender=%r msg_len=%d process=%s",
            phone,
            normalized,
            sender_id,
            msg_len,
            process_name,
        )
        if not normalized:
            _log_sms(
                sender_id=sender_id,
                recipient=phone or "",
                message=message or "",
                message_length=msg_len,
                process_name=process_name,
                status="failed",
                error_message="Invalid or empty phone number",
                created_by=created_by,
            )
            return {'success': False, 'data': None, 'message': 'Invalid or empty phone number'}

        item = {
            'user': cfg['user'],
            'pwd': cfg['pwd'],
            'number': normalized,
            'msg': message,
            'sender': sender_id,
            'language': DEFAULT_LANGUAGE,
        }
        out = _send_json_payload([item])

        if out['success']:
            ext_id = _parse_external_id(out['text'])
            _log_sms(
                sender_id=sender_id,
                recipient=normalized,
                message=message or "",
                message_length=msg_len,
                process_name=process_name,
                status="sent",
                external_id=ext_id,
                api_response_raw=out['text'],
                created_by=created_by,
            )
            return {'success': True, 'data': {'response': out['text']}, 'message': 'SMS sent'}
        _log_sms(
            sender_id=sender_id,
            recipient=normalized,
            message=message or "",
            message_length=msg_len,
            process_name=process_name,
            status="failed",
            api_response_raw=out['text'],
            error_message=out['text'],
            created_by=created_by,
        )
        return {'success': False, 'data': None, 'message': f"SMS sending failed: {out['text']}"}

    @staticmethod
    def send_messages(
        recipients: List[Dict[str, str]],
        default_sender: Optional[str] = None,
        use_last_nine: bool = True,
        process_name: str = "batch",
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send multiple SMS via mShastra JSON API. Each SMS is logged to sms_logs.

        Args:
            recipients: List of {'phone': str, 'message': str}. Optional 'sender' per item.
            default_sender: Default sender ID; overridden by recipient['sender'] if present.
            use_last_nine: Same as send_message.
            process_name: Process name for audit.
            created_by: Optional user id for audit.

        Returns:
            {'success': bool, 'data': {...}, 'message': str}
        """
        cfg = _config()
        default_sid = default_sender or cfg['sender']
        payload = []

        for r in recipients:
            phone = r.get('phone') or r.get('number')
            msg = r.get('message') or r.get('msg') or ''
            if not phone or not msg:
                continue
            normalized = _normalize_phone(phone, use_last_nine=use_last_nine)
            if not normalized:
                _log_sms(
                    sender_id=default_sid,
                    recipient=phone or "",
                    message=msg,
                    message_length=len(msg),
                    process_name=process_name,
                    status="failed",
                    error_message="Invalid or empty phone number",
                    created_by=created_by,
                )
                continue
            payload.append({
                'user': cfg['user'],
                'pwd': cfg['pwd'],
                'number': normalized,
                'msg': msg,
                'sender': r.get('sender') or default_sid,
                'language': DEFAULT_LANGUAGE,
            })

        if not payload:
            logger.warning("SMS send_messages: no valid recipients")
            return {'success': False, 'data': None, 'message': 'No valid recipients'}

        logger.info("SMS send_messages: count=%d numbers=%s", len(payload), [p['number'] for p in payload])
        out = _send_json_payload(payload)

        try:
            resp_arr = json.loads(out['text']) if out.get('text') else []
        except Exception:
            resp_arr = []

        for i, p in enumerate(payload):
            rec = p['number']
            msg = p['msg']
            sid = p['sender']
            entry = resp_arr[i] if i < len(resp_arr) and isinstance(resp_arr[i], dict) else {}
            ok = out['success'] and (entry.get('str_response') or '').lower().find('success') >= 0
            ext_id = str(entry['msg_id']) if entry.get('msg_id') else None
            _log_sms(
                sender_id=sid,
                recipient=rec,
                message=msg,
                message_length=len(msg),
                process_name=process_name,
                status="sent" if ok else "failed",
                external_id=ext_id,
                api_response_raw=json.dumps(entry) if entry else out.get('text'),
                error_message=None if ok else (out.get('text') or 'Batch send failed'),
                created_by=created_by,
            )

        if out['success']:
            return {'success': True, 'data': {'response': out['text']}, 'message': 'SMS batch sent'}
        return {'success': False, 'data': None, 'message': f"SMS batch failed: {out['text']}"}


@sms_bp.route('/api/sms/send', methods=['POST'])
def send_sms():
    """Send a single SMS. Body: { "phone": "...", "message": "...", "sender": "..." (optional) }."""
    data = request.get_json() or {}
    phone = data.get('phone')
    message = data.get('message')
    sender = data.get('sender')

    if not phone or not message:
        return jsonify({
            'success': False,
            'message': 'phone and message are required',
        }), 400

    result = SMSService.send_message(
        phone, message, sender=sender, process_name='api_send'
    )
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)


@sms_bp.route('/api/sms/send-batch', methods=['POST'])
def send_sms_batch():
    """
    Send multiple SMS. Body: {
      "recipients": [ {"phone": "...", "message": "..."}, ... ],
      "sender": "..." (optional)
    }
    """
    data = request.get_json() or {}
    recipients = data.get('recipients', [])
    sender = data.get('sender')

    if not recipients or not isinstance(recipients, list):
        return jsonify({
            'success': False,
            'message': 'recipients (array of {phone, message}) is required',
        }), 400

    result = SMSService.send_messages(
        recipients, default_sender=sender, process_name='api_send_batch'
    )
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)


def _sms_log_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row.id,
        "sender_id": row.sender_id,
        "recipient": row.recipient,
        "message": row.message,
        "message_length": row.message_length,
        "process_name": row.process_name,
        "status": row.status,
        "provider": row.provider,
        "external_id": row.external_id,
        "api_response_raw": row.api_response_raw,
        "error_message": row.error_message,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _parse_date(s: str) -> Optional[datetime]:
    """Parse YYYY-MM-DD to datetime. Returns None if empty/invalid."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


@sms_bp.route('/api/sms/logs', methods=['GET'])
@jwt_required()
def get_sms_logs():
    """
    Retrieve paginated SMS logs. Query params:
      - page (default 1)
      - per_page (default 20)
      - process_name: filter by process (e.g. registration, payment_approved)
      - status: filter by status (sent | failed)
      - recipient: filter by recipient number (partial match)
      - from_date: filter created_at >= this date (YYYY-MM-DD)
      - to_date: filter created_at <= this date (YYYY-MM-DD)
    """
    try:
        from database.db_connector import get_db
        from applications.models.models import SmsLog

        db = get_db()
        try:
            page = max(1, request.args.get('page', 1, type=int))
            per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
            process_name = request.args.get('process_name', '').strip() or None
            status = request.args.get('status', '').strip().lower() or None
            recipient = request.args.get('recipient', '').strip() or None
            from_date = _parse_date(request.args.get('from_date', ''))
            to_date = _parse_date(request.args.get('to_date', ''))

            if request.args.get('from_date', '').strip() and from_date is None:
                return jsonify({
                    "status": "error",
                    "message": "from_date must be YYYY-MM-DD",
                }), 400
            if request.args.get('to_date', '').strip() and to_date is None:
                return jsonify({
                    "status": "error",
                    "message": "to_date must be YYYY-MM-DD",
                }), 400
            if from_date is not None and to_date is not None and from_date > to_date:
                return jsonify({
                    "status": "error",
                    "message": "from_date must be on or before to_date",
                }), 400

            q = db.query(SmsLog)
            if process_name:
                q = q.filter(SmsLog.process_name == process_name)
            if status:
                q = q.filter(SmsLog.status == status)
            if recipient:
                q = q.filter(SmsLog.recipient.contains(recipient))
            if from_date is not None:
                q = q.filter(SmsLog.created_at >= from_date)
            if to_date is not None:
                end_of_day = datetime.combine(to_date.date(), time.max)
                q = q.filter(SmsLog.created_at <= end_of_day)

            total_count = q.count()
            offset = (page - 1) * per_page
            rows = (
                q.order_by(SmsLog.created_at.desc())
                .offset(offset)
                .limit(per_page)
                .all()
            )

            return jsonify({
                "status": "success",
                "message": "SMS logs retrieved successfully",
                "data": {
                    "logs": [_sms_log_to_dict(r) for r in rows],
                    "pagination": {
                        "total": total_count,
                        "page": page,
                        "per_page": per_page,
                        "total_pages": (total_count + per_page - 1) // per_page,
                    },
                },
            })
        finally:
            db.close()
    except Exception as e:
        logger.exception("get_sms_logs: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
