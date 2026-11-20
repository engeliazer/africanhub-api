"""Exercise batch payload preparation without network or database access."""
import ast
from pathlib import Path
import re
import types
import unittest
from unittest.mock import Mock


class BatchTemplateTests(unittest.TestCase):
    def setUp(self):
        self.request = Mock()
        self.service = Mock()
        self.service.send_messages.return_value = {'success': True}
        tree = ast.parse((Path(__file__).resolve().parents[1] /
                          'public/controllers/sms_controller.py').read_text())
        ns = {'request': self.request, 'SMSService': self.service, 're': re,
              'jsonify': lambda *args, **kwargs: args[0] if args else kwargs}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {'_normalize_phone', 'send_sms_batch'}:
                node.decorator_list = []
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<sms>', 'exec'), ns)
        self.route = ns['send_sms_batch']

    def test_named_recipients_get_individual_messages(self):
        self.request.get_json.return_value = {
            'message': 'Dear [NAME], welcome [NAME].',
            'recipients': [{'number': '+255712345678', 'name': 'Hamis'},
                           {'number': '+255787654321', 'name': 'Asha'}]}
        self.route()
        recipients = self.service.send_messages.call_args.args[0]
        self.assertEqual(recipients, [
            {'phone': '+255712345678', 'message': 'Dear Hamis, welcome Hamis.'},
            {'phone': '+255787654321', 'message': 'Dear Asha, welcome Asha.'}])

    def test_plain_message_remains_unchanged(self):
        self.request.get_json.return_value = {'message': 'Welcome everyone.',
            'recipients': [{'number': '+255712345678', 'name': 'Hamis'}]}
        self.route()
        self.assertEqual(self.service.send_messages.call_args.args[0][0]['message'], 'Welcome everyone.')

    def test_invalid_recipient_rejects_entire_request_before_sending(self):
        for invalid in ({'number': '+255787654321'}, {'number': '123', 'name': 'Asha'}, None):
            self.request.get_json.return_value = {'message': 'Dear [NAME]', 'recipients': [
                {'number': '+255712345678', 'name': 'Hamis'}, invalid]}
            self.assertEqual(self.route()[1], 400)
            self.service.send_messages.assert_not_called()

    def test_legacy_per_recipient_messages_are_supported(self):
        recipients = [{'phone': '+255712345678', 'message': 'Hello'}]
        self.request.get_json.return_value = {'recipients': recipients}
        self.route()
        self.assertEqual(self.service.send_messages.call_args.args[0], recipients)


if __name__ == '__main__':
    unittest.main()
