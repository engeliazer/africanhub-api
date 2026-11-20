"""Deliver temporary account credentials through independent SMS and mail channels."""
import logging

from public.controllers.sms_controller import SMSService
from public.services.mail_service import send_batch_email

logger = logging.getLogger(__name__)


def send_credential_notifications(*, phone, email, password, process_name, user_id):
    if process_name == 'registration':
        subject = 'Welcome to The African Hub'
        message = (f'Welcome to The African Hub. Your account is ready. Initial password: '
                   f'{password}. Please log in to change it.')
    else:
        subject = 'The African Hub password reset'
        message = (f'Your password for The African Hub has been reset. Your new password is: '
                   f'{password}. Please log in and change it.')
    try:
        result = SMSService.send_message(phone=phone, message=message,
                                         process_name=process_name, created_by=user_id)
        sms = {'success': bool(result['success']), 'message': result['message']}
    except Exception:
        logger.warning('Credential SMS failed for user_id=%s process=%s', user_id, process_name)
        sms = {'success': False, 'message': 'Unable to send SMS'}
    email_result = {'success': False, 'message': 'No registered email address'}
    if email:
        try:
            ok, _error = send_batch_email(from_email='', to_email=email,
                                          subject=subject, body=message, use_html=False)
            email_result = {'success': bool(ok), 'message':
                            'Email accepted by mail service' if ok else 'Unable to send email'}
        except Exception:
            logger.warning('Credential email failed for user_id=%s process=%s', user_id, process_name)
            email_result = {'success': False, 'message': 'Unable to send email'}
    return {'sms': sms, 'email': email_result}
