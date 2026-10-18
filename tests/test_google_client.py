import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from proofpage import google_docs
from proofpage.core import Store
from scripts.configure_desktop_google import configure


CLIENT = {'installed': {
    'client_id': '123456-native.apps.googleusercontent.com',
    'client_secret': 'native-client-fixture',
    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
    'token_uri': 'https://oauth2.googleapis.com/token',
    'redirect_uris': ['http://localhost'],
    'project_id': 'not-needed-in-the-distributable',
}}


class GoogleClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.client = self.root / 'native.json'
        self.client.write_text(json.dumps(CLIENT))

    def test_custom_client_precedence_and_bundled_fallback(self):
        custom = self.root / '.config/proofpage/google-oauth.json'
        bundled = self.root / 'google-desktop-client.json'
        bundled.write_text(json.dumps(CLIENT))
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'home', return_value=self.root), patch.object(google_docs, 'BUNDLED_CLIENT_FILE', bundled):
            self.assertEqual(google_docs.client_file(), bundled)
            custom.parent.mkdir(parents=True)
            custom.write_text(json.dumps(CLIENT))
            self.assertEqual(google_docs.client_file(), custom)
            with patch.dict(os.environ, {'PROOFPAGE_CONFIG_DIRECTORY': str(self.root / 'separate-profile')}):
                self.assertEqual(google_docs.client_file(), bundled)
            with patch.dict(os.environ, {'PROOFPAGE_GOOGLE_CLIENT_FILE': str(self.root / 'explicit-missing.json')}):
                self.assertEqual(google_docs.client_file(), self.root / 'explicit-missing.json')

    def test_only_official_native_metadata_is_accepted(self):
        result = google_docs.load_client_config(self.client)
        self.assertNotIn('project_id', result['installed'])
        for field, value in [('token_uri', 'https://example.invalid/token'),
                             ('auth_uri', 'https://example.invalid/auth'),
                             ('client_id', 'not-a-google-client'),
                             ('redirect_uris', ['https://example.invalid/callback'])]:
            data = copy.deepcopy(CLIENT)
            data['installed'][field] = value
            self.client.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                google_docs.load_client_config(self.client)
        for data in [{'web': CLIENT['installed']}, {'type': 'service_account', 'private_key': 'fixture'}]:
            self.client.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                google_docs.load_client_config(self.client)

    def test_user_tokens_and_private_keys_cannot_enter_a_build(self):
        for key in ['access_token', 'refresh_token', 'id_token', 'private_key', 'token']:
            data = copy.deepcopy(CLIENT)
            data['unexpected'] = [{'nested': {key: 'fixture-must-never-ship'}}]
            self.client.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                google_docs.load_client_config(self.client)
        self.client.write_bytes(b'x' * (16 * 1024 + 1))
        with self.assertRaises(ValueError):
            google_docs.load_client_config(self.client)

    def test_packaging_is_idempotent_and_refuses_replacing_identity(self):
        bundle = self.root / 'Proofpage.app'
        executables = bundle / 'Contents/MacOS'
        resources = bundle / 'Contents/Resources/proofpage'
        executables.mkdir(parents=True)
        resources.mkdir(parents=True)
        (executables / 'Proofpage-Engine').touch()
        configure(bundle, self.client)
        target = resources / 'google-desktop-client.json'
        first = target.read_bytes()
        self.assertNotIn(b'project_id', first)
        configure(bundle, self.client)
        self.assertEqual(target.read_bytes(), first)
        replacement = copy.deepcopy(CLIENT)
        replacement['installed']['client_id'] = '999-other.apps.googleusercontent.com'
        self.client.write_text(json.dumps(replacement))
        with self.assertRaisesRegex(ValueError, 'different Google client'):
            configure(bundle, self.client)
        self.assertEqual(target.read_bytes(), first)
        with self.assertRaises(ValueError):
            configure(self.root, self.client)

    def test_bundled_consent_still_uses_pkce_read_only_and_os_vault(self):
        backend = Mock()
        backend.get_password.return_value = None
        store = Store(self.root / 'workspace')
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'home', return_value=self.root), patch.object(google_docs, 'BUNDLED_CLIENT_FILE', self.client), patch.object(google_docs, 'vault', return_value=backend), patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config') as factory:
            factory.return_value.run_local_server.return_value.to_json.return_value = 'authorized-user-fixture'
            self.assertEqual(google_docs.connect(store), {'connected': True})
            self.assertEqual(factory.call_args.args[1], [google_docs.SCOPE])
            self.assertTrue(factory.call_args.kwargs['autogenerate_code_verifier'])
            consent = factory.return_value.run_local_server.call_args.kwargs
            self.assertEqual((consent['host'], consent['port'], consent['open_browser']), ('127.0.0.1', 0, True))
            backend.set_password.assert_called_once_with(google_docs.SERVICE, google_docs.account(store), 'authorized-user-fixture')
            status = google_docs.status(store)
            self.assertEqual(status['configuration_source'], 'bundled')
            self.assertNotIn(CLIENT['installed']['client_secret'], json.dumps(status))
