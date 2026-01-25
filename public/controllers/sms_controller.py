"""
SMS service using mShastra API.

Provider: mShastra (https://mshastra.com)
- JSON API: POST to sendsms_api_json.aspx
- Optional URL APIs: sendurl.aspx (single), sendurlcomma.aspx (multiple)

Env vars (recommended):
  MSHASTRA_USER     – Profile ID (e.g. AFRICANHUB)
  MSHASTRA_PWD      – Password
  MSHASTRA_SENDER   – Sender ID (e.g. AFRICANHUB)
"""

from flask import Blueprint, request, jsonify
import re
import os
import logging
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

sms_bp = Blueprint('sms', __name__)
logger = logging.getLogger(__name__)

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


class SMSService:
    @staticmethod
    def send_message(
        phone: str,
        message: str,
        sender: Optional[str] = None,
        use_last_nine: bool = True,
    ) -> Dict[str, Any]:
        """
        Send a single SMS via mShastra JSON API.

        Args:
            phone: Recipient number (e.g. 0712001002 or 255712001002).
            message: SMS text.
            sender: Sender ID override; if None, uses MSHASTRA_SENDER env.
            use_last_nine: If True, use last 9 digits + 255; else use full normalized number.

        Returns:
            {'success': bool, 'data': {...} | None, 'message': str}
        """
        cfg = _config()
        normalized = _normalize_phone(phone, use_last_nine=use_last_nine)
        logger.info(
            "SMS send_message: phone=%r normalized=%r sender=%r msg_len=%d",
            phone,
            normalized,
            sender or cfg['sender'],
            len(message or ''),
        )
        if not normalized:
            logger.warning("SMS send_message: invalid or empty phone phone=%r", phone)
            return {'success': False, 'data': None, 'message': 'Invalid or empty phone number'}

        sender_id = sender or cfg['sender']
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
            logger.info("SMS send_message: success number=%s", normalized)
            return {'success': True, 'data': {'response': out['text']}, 'message': 'SMS sent'}
        logger.warning(
            "SMS send_message: failed number=%s status=%s response=%s",
            normalized,
            out.get('status_code'),
            out['text'],
        )
        return {
            'success': False,
            'data': None,
            'message': f"SMS sending failed: {out['text']}",
        }

    @staticmethod
    def send_messages(
        recipients: List[Dict[str, str]],
        default_sender: Optional[str] = None,
        use_last_nine: bool = True,
    ) -> Dict[str, Any]:
        """
        Send multiple SMS via mShastra JSON API.

        Args:
            recipients: List of {'phone': str, 'message': str}. Optional 'sender' per item.
            default_sender: Default sender ID; overridden by recipient['sender'] if present.
            use_last_nine: Same as send_message.

        Returns:
            {'success': bool, 'data': {...}, 'message': str}
        """
        cfg = _config()
        sender_id = default_sender or cfg['sender']
        payload = []

        for r in recipients:
            phone = r.get('phone') or r.get('number')
            msg = r.get('message') or r.get('msg') or ''
            if not phone or not msg:
                continue
            normalized = _normalize_phone(phone, use_last_nine=use_last_nine)
            if not normalized:
                continue
            payload.append({
                'user': cfg['user'],
                'pwd': cfg['pwd'],
                'number': normalized,
                'msg': msg,
                'sender': r.get('sender') or sender_id,
                'language': DEFAULT_LANGUAGE,
            })

        if not payload:
            logger.warning("SMS send_messages: no valid recipients")
            return {'success': False, 'data': None, 'message': 'No valid recipients'}

        logger.info("SMS send_messages: count=%d numbers=%s", len(payload), [p['number'] for p in payload])
        out = _send_json_payload(payload)
        if out['success']:
            logger.info("SMS send_messages: success")
            return {'success': True, 'data': {'response': out['text']}, 'message': 'SMS batch sent'}
        logger.warning(
            "SMS send_messages: failed status=%s response=%s",
            out.get('status_code'),
            out['text'],
        )
        return {
            'success': False,
            'data': None,
            'message': f"SMS batch failed: {out['text']}",
        }


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

    result = SMSService.send_message(phone, message, sender=sender)
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

    result = SMSService.send_messages(recipients, default_sender=sender)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result)
