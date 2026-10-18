import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from proofpage.core import Store, recording
from proofpage.media import file_record, enrich, original


@unittest.skipUnless(importlib.util.find_spec('pypdfium2') and importlib.util.find_spec('rapidocr'), 'Install .[media] for real offline extraction checks')
class ExtractionTests(unittest.TestCase):
    def fixture(self):
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (900, 160), 'white')
        ImageDraw.Draw(image).text((20, 35), 'Original evidence 12345', font=ImageFont.load_default(size=42), fill='black')
        return image

    def test_real_image_and_scanned_pdf_ocr(self):
        from proofpage.media_worker import extract
        for format, mime in [('PNG', 'image/png'), ('PDF', 'application/pdf')]:
            with self.subTest(format=format):
                data = io.BytesIO()
                self.fixture().save(data, format=format)
                result = extract(data.getvalue(), mime)
                self.assertEqual(result['status'], 'complete')
                self.assertIn('12345', result['text'])
                self.assertEqual(result['pages'][0]['method'], 'ocr')

    def test_pdf_text_and_process_roundtrip(self):
        import pypdfium2 as pdfium
        # Minimal real PDF with selectable text, not a mocked extractor response.
        stream = b'BT /F1 24 Tf 20 80 Td (Original evidence 12345) Tj ET'
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 140] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
        data=b'%PDF-1.4\n'; offsets=[0]
        for n,obj in enumerate(objects,1):
            offsets.append(len(data));data+=str(n).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
        pos=len(data);data+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])+f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n'.encode()
        record=enrich(file_record('document.pdf',data),data)
        self.assertIn('Original evidence 12345',record['text'])
        self.assertEqual(record['metadata']['extraction']['pages'][0]['method'],'pdf-text')
        self.assertEqual(record['metadata']['extraction']['original_sha256'],hashlib.sha256(data).hexdigest())


class CollectionMediaTests(unittest.TestCase):
    def test_public_binary_collection_retains_bytes_and_repeat_dedup(self):
        data=Path('browser-companion/icons/128.png').read_bytes()
        from proofpage import core
        def fetch(url, allowed=None):
            if url.endswith('robots.txt'): return 404,{},'',url
            if '/.well-known/' in url: return 404,{},'',url
            core._RECORDER.meta.update(raw=data, header_list=[('Content-Type','image/png')], redirects=[], tls={})
            return 200,{'content-type':'image/png'},data.decode(errors='replace'),url
        with tempfile.TemporaryDirectory() as folder, patch('proofpage.core.validate_url',side_effect=lambda u:u), patch('proofpage.core.fetch',side_effect=fetch), patch('proofpage.media.enrich',side_effect=lambda r,d:r):
            store=Store(Path(folder));source=store.source('Image','web','https://example.com/photo.png')
            first=store.collect(source['id']);self.assertEqual(first['state'],'available')
            item=store.search()[0];self.assertEqual(original(store,item['current_revision'])[0],data)
            with store.db() as db: db.execute('DELETE FROM cooldowns')
            second=store.collect(source['id']);self.assertEqual(second['added'],0)
            self.assertEqual(len(store.rows('SELECT * FROM receipts')),2)
