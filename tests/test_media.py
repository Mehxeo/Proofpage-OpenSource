import base64
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from proofpage.core import Store, import_file, preview
from proofpage.media import original, bundle
from proofpage.service import get
from proofpage.adapters import parse_entry

PNG = Path('browser-companion/icons/128.png').read_bytes()
PDF = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'

class MediaTests(unittest.TestCase):
    def test_original_roundtrip_dedup_bundle_and_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            for name, data in [('seal.png', PNG), ('report.pdf', PDF)]:
                self.assertEqual(preview(name, data)[0]['records'], 1)
                result = import_file(store, name, data, [name])
                self.assertEqual(result['added'], 1)
                self.assertEqual(import_file(store, name, data, [name])['added'], 0)
                item = next(x for x in store.search() if x['title'] == name)
                rev = item['current_revision']
                saved, info = original(store, rev)
                self.assertEqual(saved, data)
                self.assertEqual(info['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(get(store, '/api/original-file/'+rev, {})[2], 'application/octet-stream')
                self.assertEqual(get(store, '/api/original-file/'+rev, {'preview':['1']})[2], 'image/png' if name.endswith('png') else 'application/octet-stream')
                with zipfile.ZipFile(io.BytesIO(bundle(store, rev))) as z:
                    manifest = json.loads(z.read('manifest.json'))
                    self.assertEqual(z.read(manifest['file']), data)
                with store.db() as db:
                    db.execute('UPDATE revisions SET raw=? WHERE id=?', (json.dumps({'data':base64.b64encode(b'changed').decode()}), rev))
                with self.assertRaises(ValueError): original(store, rev)
            self.assertEqual(store.rows('SELECT * FROM receipts'), [])

    def test_reject_mismatches_oversize_and_active_formats(self):
        for name, data in [('a.png', PDF), ('a.pdf', PNG), ('a.jpg', b'html'), ('a.webp', b'html'), ('a.png', PNG+b'0'*(8*1024*1024)), ('a.svg', b'<svg/>')]:
            with self.subTest(name=name), self.assertRaises(ValueError): parse_entry(name, data)

    def test_zip_media_entries_and_same_name_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as z:
                z.writestr('images/seal.png', PNG)
                z.writestr('report.pdf', PDF)
            self.assertEqual(len(preview('files.zip', buf.getvalue())), 2)
            self.assertEqual(import_file(store, 'files.zip', buf.getvalue(), ['images/seal.png','report.pdf'])['added'], 2)
            self.assertEqual(import_file(store, 'report.pdf', PDF, ['report.pdf'])['added'], 1)
            changed = PDF.replace(b'1.4', b'1.5')
            self.assertEqual(import_file(store, 'report.pdf', changed, ['report.pdf'])['added'], 1)
            self.assertEqual(len(store.rows('SELECT * FROM revisions')), 4)
