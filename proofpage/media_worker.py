"""Offline extraction worker, isolated so damaged files cannot hang the server."""
from contextlib import closing
import io
import json
import sys
from pathlib import Path

MAX_PAGES = 20
MAX_TEXT = 500000


def extract(data, mime):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 40000000
    engine = None
    def ocr(image):
        nonlocal engine
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        import rapidocr
        import numpy as np
        if engine is None:
            root = Path(rapidocr.__file__).parent / 'models'
            models = {'Det': 'PP-OCRv6_det_small.onnx', 'Rec': 'PP-OCRv6_rec_small.onnx', 'Cls': 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'}
            # Explicit local paths prevent the engine from downloading models at runtime.
            if any(not (root / name).is_file() for name in models.values()):
                raise ValueError('Bundled OCR models are missing.')
            engine = rapidocr.RapidOCR(params={**{key + '.model_path': str(root / name) for key, name in models.items()},
                'Global.log_level': 'error', 'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                'EngineConfig.onnxruntime.inter_op_num_threads': 1})
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((2400, 2400))
        result = engine(np.asarray(image))
        return '\n'.join(result.txts or ())
    pages = []
    total = 1
    truncated = False
    if mime == 'application/pdf':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(data) as document:
            total = len(document)
            for number in range(min(total, MAX_PAGES)):
                with closing(document[number]) as page:
                    with closing(page.get_textpage()) as textpage:
                        text = textpage.get_text_range()
                    method = 'pdf-text'
                    if not text.strip():
                        w, h = page.get_size()
                        if not w or not h:
                            raise ValueError('Invalid PDF page dimensions.')
                        scale = min(2, 2400 / max(w, h))
                        with closing(page.render(scale=scale)) as bitmap:
                            text = ocr(bitmap.to_pil())
                        method = 'ocr'
                    remaining = MAX_TEXT - sum(len(p['text']) for p in pages)
                    pages.append({'page': number + 1, 'method': method, 'text': text[:remaining]})
                    if len(text) > remaining:
                        truncated = True
                        break
    else:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40000000:
                raise ValueError('Image exceeds 40 megapixels.')
            text = ocr(image)
            pages.append({'page': 1, 'method': 'ocr', 'text': text[:MAX_TEXT]})
            truncated = len(text) > MAX_TEXT
    truncated = truncated or total > len(pages)
    text = '\n\n'.join(f"[Page {p['page']} · {p['method']}]\n{p['text']}" for p in pages)
    return {'status': 'partial' if truncated else 'complete', 'text': text, 'pages': pages,
            'total_pages': total, 'processed_pages': len(pages), 'engine': 'PDFium 5.14.0 / RapidOCR 3.10.0',
            'warning': 'Machine-extracted text may contain errors. Review it against the original before use.'}


def main():
    source, destination, mime = sys.argv[-3:]
    try:
        result = extract(Path(source).read_bytes(), mime)
    except Exception as exc:
        result = {'status': 'unavailable', 'text': '', 'pages': [], 'warning': str(exc)[:200]}
    Path(destination).write_text(json.dumps(result), encoding='utf-8')


if __name__ == '__main__':
    main()
