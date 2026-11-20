"""Gateway contract tests without application/database dependencies."""
import ast
import logging
import os
import re
import types
import unittest
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch


class SMSServiceTests(unittest.TestCase):
    def setUp(self):
        class RequestException(Exception):
            pass
        self.requests = types.SimpleNamespace(
            post=Mock(), RequestException=RequestException,
            ConnectionError=type('ConnectionError', (RequestException,), {}),
            Timeout=type('Timeout', (RequestException,), {}))
        self.log = Mock()
        self.ns = dict(os=os, re=re, uuid=uuid, sleep=Mock(), requests=self.requests,
                       logger=logging.getLogger(__name__), _log_sms=self.log,
                       Dict=Dict, List=List, Any=Any, Optional=Optional)
        tree = ast.parse((Path(__file__).resolve().parents[1] /
                          'public/controllers/sms_controller.py').read_text())
        names = {'_normalize_phone', '_config', '_send_mastercodes', 'SMSService'}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<sms>', 'exec'), self.ns)
        self.service = self.ns['SMSService']
        self.env = patch.dict(os.environ, {'MASTERCODES_SMS_SENDER_KEY': 'key',
                                          'MASTERCODES_SMS_SENDER_SECRET': 'secret'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def response(self, status=200, body=None):
        return Mock(status_code=status, text='provider response',
                    json=Mock(return_value=body if body is not None else
                              {'data': {'messages': [{'status': 'sent', 'id': 17}]}}))

    def test_accepted_request_contract_and_audit(self):
        self.requests.post.return_value = self.response()
        self.assertTrue(self.service.send_message('0755344162', 'hello')['success'])
        args, kw = self.requests.post.call_args
        self.assertEqual(args[0], 'https://api.mastercodes.co.tz/api/v1/gateway/sms/send')
        self.assertEqual(kw['json']['recipient'], '+255755344162')
        self.assertEqual(kw['json']['message'], 'hello')
        uuid.UUID(kw['json']['request_id'])
        self.assertEqual(kw['headers']['X-Sender-Secret'], 'secret')
        self.assertEqual(kw['timeout'], (5, 10))
        self.assertFalse(kw['allow_redirects'])
        self.assertEqual(self.log.call_args.kwargs['external_id'], '17')

    def test_http_200_rejection_and_malformed_bodies_fail(self):
        for body in ({'data': {'messages': [{'status': 'failed'}]}}, {}, [],
                     {'data': None}, {'data': {'messages': None}}):
            self.requests.post.return_value = self.response(body=body)
            self.assertFalse(self.service.send_message('0755344162', 'hello')['success'])
            self.assertEqual(self.log.call_args.kwargs['status'], 'failed')
        self.requests.post.return_value = self.response(status=401)
        self.assertFalse(self.service.send_message('0755344162', 'hello')['success'])

    def test_invalid_json_and_redirect_are_not_accepted(self):
        response = self.response()
        response.json.side_effect = ValueError('invalid JSON')
        self.requests.post.return_value = response
        self.assertFalse(self.service.send_message('0755344162', 'hello')['success'])
        self.requests.post.return_value = self.response(status=302)
        self.assertFalse(self.service.send_message('0755344162', 'hello')['success'])

    def test_retry_preserves_request_id_and_payload(self):
        self.requests.post.side_effect = [self.requests.Timeout(), self.response()]
        self.assertTrue(self.service.send_message('0755344162', 'hello')['success'])
        self.assertEqual(self.requests.post.call_args_list[0], self.requests.post.call_args_list[1])

    def test_5xx_retry_and_timeout_exhaustion(self):
        self.requests.post.side_effect = [self.response(503), self.response()]
        self.assertTrue(self.service.send_message('0755344162', 'hello')['success'])
        self.requests.post.reset_mock(side_effect=True)
        self.requests.post.side_effect = self.requests.Timeout()
        self.assertFalse(self.service.send_message('0755344162', 'hello')['success'])
        self.assertEqual(self.requests.post.call_count, 2)

    def test_missing_credentials_and_invalid_number_do_not_send(self):
        with patch.dict(os.environ, {'MASTERCODES_SMS_SENDER_SECRET': ''}):
            self.assertFalse(self.service.send_message('0755344162', 'hello')['success'])
        self.assertFalse(self.service.send_message('123', 'hello')['success'])
        self.requests.post.assert_not_called()

    def test_batch_reports_partial_failure(self):
        self.requests.post.return_value = self.response()
        result = self.service.send_messages([{'phone': '0755344162', 'message': 'hello'},
                                             {'phone': '123', 'message': 'hello'}])
        self.assertFalse(result['success'])
        self.assertEqual(result['data']['accepted'], 1)
        self.assertEqual(result['data']['failed'], 1)
        self.assertEqual(self.log.call_count, 2)

    def test_bulk_audit_keeps_name_batch_personalized_message_and_response(self):
        self.requests.post.return_value = self.response()
        self.service.send_messages([
            {'number': '+255712345678', 'name': 'Hamis', 'message': 'Dear Hamis'},
            {'number': '+255787654321', 'name': 'Asha', 'message': 'Dear Asha'},
        ], batch_name='Welcome November')
        records = [c.kwargs for c in self.log.call_args_list]
        self.assertEqual([r['recipient_name'] for r in records], ['Hamis', 'Asha'])
        self.assertEqual([r['message'] for r in records], ['Dear Hamis', 'Dear Asha'])
        self.assertEqual([r['recipient'] for r in records], ['+255712345678', '+255787654321'])
        for record in records:
            self.assertEqual(record['category'], 'bulk')
            self.assertEqual(record['batch_name'], 'Welcome November')
            self.assertEqual(record['api_response_raw'], 'provider response')

    def test_database_row_contains_audit_metadata_and_segment_count(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] /
                          'public/controllers/sms_controller.py').read_text())
        session, model = Mock(), Mock()
        ns = dict(self.ns, _get_session_and_model=lambda: (lambda: session, model))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {'_sms_count_from_length', '_log_sms'}:
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<audit>', 'exec'), ns)
        ns['_log_sms'](sender_id='AFRICANHUB', recipient='+255712345678',
                       message='x' * 161, message_length=161, process_name='api_send_batch',
                       status='sent', recipient_name='Hamis', category='bulk', batch_name='Welcome',
                       api_response_raw='provider response')
        row = model.call_args.kwargs
        self.assertEqual(row['sms_count'], 2)
        self.assertEqual(row['provider'], 'mastercodes')
        self.assertEqual(row['recipient_name'], 'Hamis')
        self.assertEqual(row['batch_name'], 'Welcome')
        self.assertEqual(row['category'], 'bulk')
        self.assertEqual(row['message'], 'x' * 161)
        session.add.assert_called_once_with(model.return_value)
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_single_audit_defaults_and_optional_name(self):
        self.requests.post.return_value = self.response()
        self.service.send_message('0755344162', 'hello', recipient_name='Hamis')
        record = self.log.call_args.kwargs
        self.assertEqual(record['category'], 'single')
        self.assertIsNone(record['batch_name'])
        self.assertEqual(record['recipient_name'], 'Hamis')

    def test_international_number_is_preserved(self):
        normalize = self.ns['_normalize_phone']
        self.assertEqual(normalize('+254712345678'), '+254712345678')
        self.assertEqual(normalize('255755344162'), '+255755344162')
        self.assertEqual(normalize('755344162'), '+255755344162')


if __name__ == '__main__':
    unittest.main()
