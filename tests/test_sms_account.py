import ast
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlparse

class AccountTests(unittest.TestCase):
    def setUp(self):
        self.requests = Mock()
        self.requests.RequestException = RuntimeError
        blueprint = Mock()
        blueprint.route.side_effect = lambda *a, **k: lambda fn: fn
        def jsonify(**kw):
            result = Mock()
            result.payload = kw
            result.headers = {}
            return result
        self.ns = dict(urlparse=urlparse, requests=self.requests, sms_bp=blueprint,
                       jwt_required=lambda: lambda fn: fn, jsonify=jsonify,
                       _config=lambda: dict(key='key', secret='secret', url='https://gateway/sms'))
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'public/controllers/sms_controller.py').read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {'_safe_sms_url', '_sms_account_request', 'get_sms_balance', 'get_sms_portal_access'}:
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<account>', 'exec'), self.ns)

    def gateway(self, method, data, status=200):
        getattr(self.requests, method).return_value = Mock(status_code=status, json=lambda: {'data': data})

    def test_zero_balance_and_no_credentials_leaked(self):
        self.gateway('get', {'available_units': 0, 'secret': 'hidden'})
        response = self.ns['get_sms_balance']()
        self.assertEqual(response.payload['data'], {'available_units': 0})
        self.assertFalse(self.requests.get.call_args.kwargs['allow_redirects'])
        self.assertEqual(self.requests.get.call_args.kwargs['timeout'], (5, 10))

    def test_invalid_balances_and_upstream_failure(self):
        for units in [None, '0', True, -1, float('nan'), float('inf')]:
            self.gateway('get', {'available_units': units})
            self.assertEqual(self.ns['get_sms_balance']()[1], 502)
        self.gateway('get', {'available_units': 10}, status=503)
        self.assertEqual(self.ns['get_sms_balance']()[1], 502)

    def test_portal_validation_and_cache_headers(self):
        for url, expiry, status in [('https://www.mastercodes.co.tz/sms/access#ticket=x',60,200),
                                     ('http://mastercodes.co.tz/x',60,502),
                                     ('https://evil.test/x',60,502),
                                     ('https://mastercodes.co.tz/x',0,502),
                                     ('https://mastercodes.co.tz/x',True,502)]:
            self.gateway('post', {'url':url,'expires_in':expiry})
            response, code = self.ns['get_sms_portal_access']()
            self.assertEqual(code,status)
            self.assertEqual(response.headers['Cache-Control'],'no-store, private')

    def test_network_and_malformed_json_fail_safely(self):
        self.requests.get.side_effect = RuntimeError('secret upstream error')
        response, code = self.ns['get_sms_balance']()
        self.assertEqual(code,502)
        self.assertNotIn('secret', response.payload['message'])
        self.requests.get.side_effect = None
        self.requests.get.return_value = Mock(status_code=200)
        self.requests.get.return_value.json.side_effect = ValueError('bad JSON')
        self.assertEqual(self.ns['get_sms_balance']()[1],502)

if __name__ == '__main__': unittest.main()
