import unittest
from unittest.mock import patch
from proofpage import updates


class UpdateTests(unittest.TestCase):
    def release(self, tag='v0.4.1', url=None):
        name = f'Proofpage-{tag[1:]}-darwin-arm64.zip'
        return {'tag_name': tag, 'assets': [{'name': name, 'state': 'uploaded',
                'browser_download_url': url or f'{updates.RELEASES}/download/{tag}/{name}'}]}

    @patch('proofpage.updates.platform.machine', return_value='arm64')
    @patch('proofpage.updates.platform.system', return_value='Darwin')
    @patch('proofpage.updates.CURRENT', '0.4.0')
    def test_platform_download_and_numeric_version(self, *_):
        self.assertTrue(updates.release_info(self.release('v0.4.10'))['available'])
        self.assertIsNotNone(updates.release_info(self.release())['download'])
        for tag in ('v0.4.0', 'v0.2.9'):
            result = updates.release_info(self.release(tag))
            self.assertFalse(result['available'])
            self.assertIsNone(result['download'])
        self.assertIsNone(updates.release_info(self.release(url='https://example.org/app.zip'))['download'])

    def test_reject_unstable_and_invalid_releases(self):
        for data in ({'tag_name':'v0.3.2-beta'}, {'tag_name':'v0.3.2', 'draft':True},
                     {'tag_name':'v0.3.2','prerelease':True}, {}):
            with self.assertRaises(ValueError): updates.release_info(data)

    @patch('proofpage.updates.urllib.request.urlopen', side_effect=OSError('offline'))
    def test_offline_is_not_reported_as_up_to_date(self, _):
        with self.assertRaisesRegex(ValueError, 'Could not check'):
            updates.check()
