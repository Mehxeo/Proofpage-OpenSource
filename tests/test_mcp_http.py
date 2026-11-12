import importlib.util
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

@unittest.skipUnless(importlib.util.find_spec('mcp') and importlib.util.find_spec('jwt'), 'optional mcp-http extra')
class HTTPMCPTests(unittest.TestCase):
    def test_oauth_read_only_transport(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from starlette.testclient import TestClient
        from proofpage.core import Store
        from proofpage import business
        from proofpage.mcp_http import create_server
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        config = {'url': 'https://proofpage.example/mcp', 'issuer': 'https://issuer.example/', 'jwks_url': 'https://issuer.example/jwks', 'subject': 'owner'}
        claims = {'sub': 'owner', 'iss': config['issuer'], 'aud': config['url'], 'exp': int(time.time()) + 300, 'scope': 'proofpage:read'}
        def token(**changes): return jwt.encode({**claims, **changes}, key, algorithm='RS256', headers={'kid': 'test'})
        with tempfile.TemporaryDirectory() as directory, patch('jwt.PyJWKClient.get_signing_key_from_jwt', return_value=SimpleNamespace(key=key.public_key())):
            store = Store(directory)
            private = store.source('Private Google title', 'import', 'google-doc:fictional-http-doc')
            store.save(private['id'], 'doc', 'text', 'Private Google title', 'Private business strategy.', '{}', {'adapter': 'google_docs'})
            revision = store.rows('SELECT id FROM revisions')[0]['id']
            profile = business.create(store, 'Private profile')['id']
            business.attach(store, profile, revision, 'business')
            fact = business.draft(store, profile)['facts'][0]
            business.review(store, fact['id'], fact['text'], 'approved', True, True)
            server = create_server(store, config)
            with TestClient(server.streamable_http_app()) as client:
                headers = {'Host': '127.0.0.1:8910', 'Accept': 'application/json, text/event-stream'}
                metadata = client.get('/.well-known/oauth-protected-resource/mcp', headers=headers)
                self.assertEqual(metadata.status_code, 200, metadata.text)
                self.assertEqual(metadata.json()['resource'], config['url'])
                self.assertEqual(metadata.json()['authorization_servers'], [config['issuer']])
                message = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}}
                self.assertEqual(client.post('/mcp', json=message, headers=headers).status_code, 401)
                for invalid in (token(sub='other'), token(aud='another-service'), token(exp=1), token(scope='other')):
                    self.assertEqual(client.post('/mcp', json=message, headers={**headers, 'Authorization': 'Bearer ' + invalid}).status_code, 401)
                headers['Authorization'] = 'Bearer ' + token()
                result = client.post('/mcp', json=message, headers=headers)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertIn('protocolVersion', result.json()['result'])
                tools = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, headers=headers).json()['result']['tools']
                names = {t['name'] for t in tools}
                self.assertIn('proofpage_business_context', names)
                self.assertNotIn('proofpage_collect', names)
                call = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'proofpage_business_profiles', 'arguments': {}}}, headers=headers)
                self.assertFalse(call.json()['result'].get('isError'))
                self.assertEqual(call.json()['result']['structuredContent']['result'], [])
                blocked = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'proofpage_business_context', 'arguments': {'profile_id': profile}}}, headers=headers)
                self.assertTrue(blocked.json()['result']['isError'])
                self.assertNotIn('Private business strategy.', blocked.text)
                filtered = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'proofpage_get_context', 'arguments': {'query': 'strategy'}}}, headers=headers)
                self.assertFalse(filtered.json()['result'].get('isError'))
                self.assertNotIn('Private business strategy.', filtered.text)
                denied = client.post('/mcp', json=message, headers={**headers, 'Origin': 'https://evil.example'})
                self.assertEqual(denied.status_code, 403)
