"""Check independent channel delivery without sending real credentials."""
import ast
import logging
from pathlib import Path
import unittest
from unittest.mock import Mock


class CredentialNotificationTests(unittest.TestCase):
    def setUp(self):
        self.sms = Mock()
        self.sms.send_message.return_value = {'success': True, 'message': 'accepted'}
        self.mail = Mock(return_value=(True, None))
        ns = {'SMSService': self.sms, 'send_batch_email': self.mail,
              'logger': logging.getLogger(__name__)}
        path = Path(__file__).resolve().parents[1] / 'auth/services/credential_notifications.py'
        tree = ast.parse(path.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
        self.send = ns['send_credential_notifications']

    def deliver(self, process='registration', email='recipient@example.com'):
        return self.send(phone='255700000001', email=email, password='123456',
                         process_name=process, user_id=190)

    def test_both_flows_send_same_credential_to_both_channels(self):
        for process in ('registration', 'password_reset'):
            with self.subTest(process=process):
                result = self.deliver(process)
                self.assertTrue(result['sms']['success'])
                self.assertTrue(result['email']['success'])
                sms = self.sms.send_message.call_args.kwargs
                mail = self.mail.call_args.kwargs
                self.assertIn('123456', mail['body'])
                self.assertEqual(sms['message'], mail['body'])
                self.assertEqual(sms['process_name'], process)
                self.assertEqual(mail['to_email'], 'recipient@example.com')
                self.assertEqual(mail['from_email'], '')
                self.assertFalse(mail['use_html'])

    def test_sms_exception_does_not_block_email(self):
        self.sms.send_message.side_effect = RuntimeError('SMS failure')
        result = self.deliver()
        self.assertFalse(result['sms']['success'])
        self.assertTrue(result['email']['success'])
        self.mail.assert_called_once()

    def test_rejected_sms_does_not_block_email(self):
        self.sms.send_message.return_value = {'success': False, 'message': 'rejected'}
        result = self.deliver()
        self.assertFalse(result['sms']['success'])
        self.assertTrue(result['email']['success'])

    def test_mail_exception_or_rejection_preserves_sms_success(self):
        self.mail.side_effect = RuntimeError('mail failure')
        result = self.deliver('password_reset')
        self.assertTrue(result['sms']['success'])
        self.assertFalse(result['email']['success'])
        self.mail.side_effect = None
        self.mail.return_value = (False, 'provider rejected')
        self.assertFalse(self.deliver()['email']['success'])

    def test_missing_email_does_not_prevent_sms(self):
        result = self.deliver(email=None)
        self.assertTrue(result['sms']['success'])
        self.assertFalse(result['email']['success'])
        self.mail.assert_not_called()


if __name__ == '__main__':
    unittest.main()
