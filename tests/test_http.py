import base64
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.process = subprocess.Popen([sys.executable, '-m', 'proofpage', '--home', cls.temp.name, 'serve', '--port', str(cls.port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.base + '/api/session', timeout=1) as response:
                    cls.token = json.load(response)['token']
                break
            except (OSError, urllib.error.URLError):
                if cls.process.poll() is not None:
                    raise RuntimeError(cls.process.stderr.read().decode())
                time.sleep(.05)
        else:
            cls.process.terminate()
            raise RuntimeError('Server did not start.')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.communicate(timeout=5)
        cls.temp.cleanup()

    def request(self, path, data=None, headers=None):
        request = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                                         headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json', **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read().decode()
            return response.status, json.loads(body) if response.headers.get_content_type() == 'application/json' else body

    def test_mcp_connection_check_requires_session(self):
        self.assertEqual(self.request('/api/mcp-check', {}, {'Authorization': ''})[0], 401)
        status, result = self.request('/api/mcp-check', {})
        self.assertEqual(status, 200)
        self.assertTrue(result['ok'], result)
        self.assertGreater(result['tools'], 0)
        self.assertIn('proofpage_business_profiles', result['checks'])

    def test_assistant_kit_download_is_authenticated_and_client_specific(self):
        import io
        import tomllib
        import zipfile
        from pathlib import Path
        self.assertEqual(self.request('/api/assistant-kit?client=codex', headers={'Authorization': ''})[0], 401)
        self.assertEqual(self.request('/api/assistant-kit?client=web')[0], 400)
        request = urllib.request.Request(self.base + '/api/assistant-kit?client=codex', headers={'Authorization': 'Bearer ' + self.token})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.headers.get_content_type(), 'application/zip')
            body = response.read()
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            self.assertIn('.agents/skills/proofpage/SKILL.md', archive.namelist())
            config = tomllib.loads(archive.read('mcp-config.toml').decode())
            self.assertIn(str(Path(self.temp.name).resolve()), config['mcp_servers']['proofpage']['args'])

    def test_google_selection_errors_are_specific_without_fetching(self):
        status, result = self.request('/api/google-docs/select', {'document': 'bad-link', 'owner_permission': True})
        self.assertEqual(status, 400)
        self.assertIn('valid Google Docs document', result['error'])
        self.assertNotIn('bad-link', result['error'])

    def test_companion_pair_import_and_revocation(self):
        origin = 'chrome-extension://' + 'a' * 32
        other = 'chrome-extension://' + 'b' * 32
        headers = {'Origin': origin, 'Authorization': ''}
        self.assertEqual(self.request('/api/companion/pair', {'code': 'no'}, headers)[0], 403)
        code = self.request('/api/companion-code', {})[1]['code']
        self.assertEqual(self.request('/api/companion/pair', {'code': code}, {'Origin': 'https://evil.example'})[0], 403)
        status, paired = self.request('/api/companion/pair', {'code': code}, headers)
        self.assertEqual(status, 200)
        self.assertEqual(self.request('/api/companion/pair', {'code': code}, headers)[0], 403)
        headers['Authorization'] = 'Bearer ' + paired['token']
        self.assertEqual(self.request('/api/state', headers=headers)[0], 403)
        self.assertEqual(self.request('/api/state', headers={'Authorization': headers['Authorization']})[0], 401)
        capture = {'proofpage_capture': 'visible-text-v1', 'url': 'https://example.com/companion', 'text': 'Reviewed text', 'title': 'Companion test'}
        payload = {'reviewed': True, 'capture': capture}
        self.assertEqual(self.request('/api/companion/import', payload, dict(headers, Origin=other))[0], 401)
        self.assertEqual(self.request('/api/companion/import', {'capture': capture}, headers)[0], 400)
        status, result = self.request('/api/companion/import', payload, headers)
        self.assertEqual(status, 200)
        self.assertEqual(result['added'], 1)
        self.assertEqual(self.request('/api/companion/import', payload, headers)[1]['added'], 0)
        self.request('/api/companion-revoke', {})
        self.assertEqual(self.request('/api/companion/import', payload, headers)[0], 401)

    def test_companion_original_file_and_authenticated_download(self):
        from pathlib import Path
        original = Path('browser-companion/icons/128.png').read_bytes()
        code = self.request('/api/companion-code', {})[1]['code']
        headers = {'Origin': 'chrome-extension://' + 'd' * 32}
        paired = self.request('/api/companion/pair', {'code': code}, headers)[1]
        headers['Authorization'] = 'Bearer ' + paired['token']
        payload = {'filename':'actual.png', 'data':base64.b64encode(original).decode(), 'reviewed':True}
        self.assertEqual(self.request('/api/companion/import-file', dict(payload, reviewed=False), headers)[0], 400)
        self.assertEqual(self.request('/api/companion/import-file', dict(payload, filename='fake.pdf'), headers)[0], 400)
        self.assertEqual(self.request('/api/companion/import-file', dict(payload, data='bad!'), headers)[0], 400)
        status, saved = self.request('/api/companion/import-file', payload, headers)
        self.assertEqual((status, saved['added']), (200, 1))
        self.assertEqual(self.request('/api/companion/import-file', payload, headers)[1]['added'], 0)
        item = next(i for i in self.request('/api/state')[1]['items'] if i['title']=='actual.png')
        route = '/api/original-file/' + item['current_revision']
        self.assertEqual(self.request(route, headers={'Authorization':''})[0], 401)
        req = urllib.request.Request(self.base+route, headers={'Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.headers.get_content_type(), 'application/octet-stream')
            self.assertEqual(response.read(), original)
        self.request('/api/companion-revoke', {})
        self.assertEqual(self.request('/api/companion/import-file', payload, headers)[0], 401)

    def test_companion_url_review_auth_and_private_address_guards(self):
        code = self.request('/api/companion-code', {})[1]['code']
        headers = {'Origin': 'chrome-extension://' + 'a' * 32}
        paired = self.request('/api/companion/pair', {'code': code}, headers)[1]
        headers['Authorization'] = 'Bearer ' + paired['token']
        payload = {'reviewed': True, 'url': 'http://127.0.0.1/private.png'}
        self.assertEqual(self.request('/api/companion/import-url', dict(payload, reviewed=False), headers)[0], 400)
        self.assertEqual(self.request('/api/companion/import-url', payload, headers)[0], 400)
        self.request('/api/companion-revoke', {})
        self.assertEqual(self.request('/api/companion/import-url', payload, headers)[0], 401)

    def test_companion_pair_attempt_limit(self):
        code = self.request('/api/companion-code', {})[1]['code']
        headers = {'Origin': 'chrome-extension://' + 'c' * 32}
        for _ in range(10):
            self.assertEqual(self.request('/api/companion/pair', {'code': 'wrong'}, headers)[0], 403)
        self.assertEqual(self.request('/api/companion/pair', {'code': code}, headers)[0], 403)

    def test_host_origin_and_session_enforced(self):
        self.assertEqual(self.request('/api/state', headers={'Authorization': ''})[0], 401)
        self.assertEqual(self.request('/api/state', headers={'Origin': 'https://untrusted.example'})[0], 403)
        self.assertEqual(self.request('/api/session', headers={'Host': 'untrusted.example'})[0], 403)
        self.assertEqual(self.request('/api/session', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_static_assets_typed_and_contained(self):
        for path, kind in (('/', 'text/html'), ('/ui.js', 'text/javascript'), ('/style.css', 'text/css'), ('/icons.svg', 'image/svg+xml'), ('/favicon.svg', 'image/svg+xml'),
                           ('/fonts/newsreader-latin-opsz-normal.woff2', 'font/woff2'), ('/fonts/jetbrains-mono-latin-wght-normal.woff2', 'font/woff2'), ('/fonts/ibm-plex-sans-latin.woff2', 'font/woff2')):
            with urllib.request.urlopen(self.base + path, timeout=5) as response:
                self.assertEqual(response.headers.get_content_type(), kind, path)
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
                self.assertIn("style-src 'self';", response.headers['Content-Security-Policy'])
                if kind == 'font/woff2':
                    self.assertEqual(response.headers['Content-Type'], 'font/woff2')
                    self.assertEqual(response.read(4), b'wOF2')
        for path in ('/../core.py', '/%2e%2e/core.py', '/static/../core.py', '/index.html', '/.hidden.js', '/missing.js', '/assets.py', '/fonts/OFL-Newsreader.txt', '/fonts/README.md'):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_full_import_review_freeze_export_revoke_flow(self):
        status, profile = self.request('/api/profiles', {'name': 'HTTP test', 'provider': 'fixture', 'account': 'test', 'adapter': 'generic'})
        self.assertEqual(status, 200)
        data = {'filename': 'record.md', 'data': base64.b64encode(b'Synthetic local evidence for API validation.').decode()}
        status, preview = self.request('/api/preview', data)
        self.assertEqual((status, preview[0]['records']), (200, 1))
        structured = {'filename': 'record.json', 'data': base64.b64encode(b'[]').decode(), 'selected': ['record.json']}
        self.assertEqual(self.request('/api/import', structured)[0], 400)
        status, result = self.request('/api/import', {**data, 'selected': ['record.md'], 'profile_id': profile['id']})
        self.assertEqual((status, result['added']), (200, 1))
        _, state = self.request('/api/state?q=Synthetic')
        item = state['items'][0]
        _, detail = self.request('/api/items/' + item['id'])
        self.assertEqual(detail['review']['allowed'], 0)
        review = {'revision_id': item['current_revision'], 'allowed': True, 'approved': True}
        self.assertEqual(self.request('/api/review', review)[0], 200)
        _, dataset = self.request('/api/freeze', {'name': 'HTTP frozen corpus'})
        status, exported = self.request('/api/export/' + dataset['id'])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(exported)['text'], 'Synthetic local evidence for API validation.')
        self.request('/api/review', {**review, 'allowed': False})
        self.assertEqual(self.request('/api/export/' + dataset['id'])[0], 400)

    def test_plain_file_import_without_account_setup_is_authenticated(self):
        payload = {'filename': 'local-onboarding.txt', 'data': base64.b64encode(b'Unique onboarding file for plain local import.').decode(), 'selected': ['local-onboarding.txt'], 'profile_id': ''}
        self.assertEqual(self.request('/api/import', payload, {'Authorization': ''})[0], 401)
        status, result = self.request('/api/import', payload)
        self.assertEqual((status, result['added']), (200, 1))
        self.assertEqual(self.request('/api/import', payload)[1]['added'], 0)
        self.assertEqual(self.request('/api/business-evidence', headers={'Authorization': ''})[0], 401)
        status, evidence = self.request('/api/business-evidence?q=onboarding')
        self.assertEqual(status, 200)
        self.assertEqual(evidence[0]['title'], 'local-onboarding')
        detail = self.request('/api/items/' + evidence[0]['id'])[1]
        self.assertFalse(detail['review']['approved'])

    def test_training_api_flow(self):
        _, profile = self.request('/api/profiles', {'name':'Training fixture','provider':'fixture','account':'training','adapter':'generic'})
        data = {'filename':'training.md','data':base64.b64encode(b'Fixture plants use sunlight.').decode(),'selected':['training.md'],'profile_id':profile['id']}
        self.assertEqual(self.request('/api/import',data)[0],200)
        _, state = self.request('/api/state?q=sunlight')
        rev = state['items'][0]['current_revision']
        status, candidate = self.request('/api/candidate',{'revision_id':rev,'kind':'correction','payload':{'prompt':'Energy?','completion':'Sunlight.'},'quote':'plants use sunlight'})
        self.assertEqual(status,200)
        self.assertEqual(self.request('/api/candidate-review',{'candidate_id':candidate['id'],'decision':'approved'})[0],400)
        self.request('/api/review',{'revision_id':rev,'allowed':True,'approved':False})
        self.assertEqual(self.request('/api/candidate-review',{'candidate_id':candidate['id'],'decision':'approved'})[0],200)
        status, dataset = self.request('/api/training-freeze',{'name':'API bundle','candidate_ids':[candidate['id']],'kind':'correction'})
        self.assertEqual(status,200)
        self.assertEqual(dataset['splits']['train'],1)
        request = urllib.request.Request(self.base+'/api/bundle/'+dataset['id'],headers={'Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.read(2),b'PK')
        self.request('/api/candidate-review',{'candidate_id':candidate['id'],'decision':'revoked'})
        self.assertEqual(self.request('/api/bundle/'+dataset['id'])[0],400)
        self.assertEqual(self.request('/api/workbench')[0],200)
        self.assertEqual(self.request('/workbench.js')[0],200)

    def test_invalid_archive_returns_controlled_error(self):
        self.assertEqual(self.request('/api/preview', {'filename': 'bad.zip', 'data': base64.b64encode(b'invalid').decode()})[0], 400)


if __name__ == '__main__':
    unittest.main()
