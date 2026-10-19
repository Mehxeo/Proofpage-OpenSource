# Images, PDFs, and automatic collection

Proofpage 0.3 saves original PNG, JPEG, WebP, and PDF files and makes their text searchable. The desktop download includes the extraction engines and OCR models: no Python installation, terminal, model account, or cloud upload is needed.

## Save a file

Choose **Import files**, select a file, review the preview, and import it. Open its Library card to read extracted text, preview an image, download the unchanged original, or download a bundle with its SHA-256, extracted text, and extraction details.

PDFs with selectable text use PDFium. Pages without selectable text are rendered locally and passed through RapidOCR. Images use RapidOCR. Every extracted page records its method and page number. Extraction is machine-generated and needs checking, especially handwriting, small text, complex layouts, and unusual languages. A successful extraction is not a claim of perfect transcription. Mixed pages with selectable text use that text layer; diagrams on those pages are not separately OCRed.

Originals remain available when extraction fails, a PDF needs a password, or an optional engine is missing. Existing captures are not silently rewritten: reimport an older file to add an extracted revision. Text and extraction metadata are linked to the original SHA-256.

## Save directly from a website

In the 0.3 companion, choose **Preview this page**, open **Save an image directly from this page**, choose an image, confirm permission, and click **Save web file**. You can also paste a public image or PDF URL there. Nothing needs to be downloaded to your Downloads folder first. Pair with the running app once in Settings → Connect browser.

Alternatively, paste an image or PDF URL in the app's **Add source** dialog and collect it. Public URL collection observes robots.txt, public-network restrictions, rate limits, and redirects. It does not send browser cookies or passwords. Signed/query-dependent image URLs may require pasting the complete public URL; the page preview intentionally strips query strings. Do not paste secrets. Private/session-only files can still be imported from a user-supplied file.

The [Chrome Web Store companion](https://chromewebstore.google.com/detail/proofpage-%E2%80%94-save-page-evi/kiiobhppgpjpccapcejhnagfneopcppk) is now published as 0.3.0 and includes these file controls. Install it with Add to Chrome; Developer mode is not needed. The newer 0.3.1 source UI is separate and has not been published to the store.

## Automate it

On a source card, click **Watch hourly**. While the desktop app is running, Proofpage collects that URL every hour, extracts text, preserves changed revisions, and adds changes to Timeline. Click **Stop watching** to stop. This works for HTML, supported images, and PDFs. It does not crawl every linked asset automatically.

Folder watches also accept PNG, JPEG, WebP, and PDF files, using the existing exact-filename category selection. CLI `collect`, scheduled sources, crawl jobs, and MCP collection all use the same collector. Keep the app or `proofpage serve` running; schedules do not run while your computer sleeps or the app is closed.

## Limits and installation

- 8 MiB per original; PNG and decoded image limit of 40 megapixels.
- At most 20 PDF pages and 500,000 extracted characters per file. The result says **partial** when these limits truncate it.
- OCR images are scaled to at most 2,400 pixels per side. Animated images are not supported as complete animations.
- Each extraction runs in a separate process with a 90-second timeout. One extraction runs at a time. Damaged files cannot indefinitely block collection, but file parsing is not a malware scanner or an OS security sandbox.
- OCR inference uses bundled local models. It does not call an AI provider or download a model at runtime.
- Source installs keep their lightweight default. Install `pip install '.[media]'` for PDF/OCR support. Desktop builds include it.

Engines: [PDFium through pypdfium2](https://github.com/pypdfium2-team/pypdfium2), [RapidOCR](https://github.com/RapidAI/RapidOCR), and ONNX Runtime. Their licenses and bundled notices ship with the packaged dependencies.
