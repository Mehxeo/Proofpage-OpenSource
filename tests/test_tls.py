import ssl
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from proofpage.tls import context


class TlsTests(unittest.TestCase):
    def test_verification_and_hostname_checks_stay_enabled(self):
        result=context()
        self.assertEqual(result.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(result.check_hostname)

    def test_system_ca_fallback_only_when_default_bundle_missing(self):
        result=Mock()
        with patch('proofpage.tls.ssl.create_default_context',return_value=result),patch('proofpage.tls.ssl.get_default_verify_paths',return_value=SimpleNamespace(cafile=None)),patch('proofpage.tls.Path.is_file',return_value=True):
            self.assertIs(context(),result)
        result.load_verify_locations.assert_called_once_with('/etc/ssl/cert.pem')
