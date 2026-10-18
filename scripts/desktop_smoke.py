"""Launch the packaged GUI and check its real HTTP API, without a Python child."""
import json
from pathlib import Path
import platform
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
system = platform.system()
if system == 'Darwin':
    app = root / 'build/desktop/Proofpage.app/Contents/MacOS/Proofpage'
else:
    app = root / 'build/desktop/Proofpage' / ('Proofpage.exe' if system == 'Windows' else 'Proofpage')
with tempfile.TemporaryDirectory(prefix='proofpage-desktop-') as directory:
    report = Path(directory) / 'result.json'
    try:
        result = subprocess.run([str(app), '--smoke-test', str(report)], cwd=directory, timeout=90, capture_output=True, text=True)
    finally:
        log = Path.home() / 'Proofpage/launcher.log'
        if log.exists():
            print(log.read_text(encoding='utf-8', errors='replace')[-12000:])
        if report.exists():
            print(report.read_text())
    if result.returncode or not report.exists():
        raise RuntimeError(f'Desktop failed: {result.returncode}\n{result.stdout}\n{result.stderr}')
    data = json.loads(report.read_text())
    assert data['ready'] and data['gui'], data
    assert data['google_oauth'], data
    assert (report.parent / 'workspace/data/proofpage.sqlite3').exists()
    print('Packaged native GUI, bundled Python, SQLite, HTTP API, and shutdown passed.')

    entry = data['mcp']
    requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'proofpage_list_sources','arguments':{}}}]
    rpc = subprocess.run([entry['command'], *entry['args']], input=''.join(json.dumps(r)+'\n' for r in requests), capture_output=True, text=True, timeout=30, check=True)
    replies = [json.loads(line) for line in rpc.stdout.splitlines()]
    assert len(replies) == 3, replies
    tool_names = {tool['name'] for tool in replies[1]['result']['tools']}
    assert {'proofpage_verify_quotes', 'proofpage_check_answer', 'proofpage_get_receipt', 'proofpage_get_rights', 'proofpage_diff_revisions',
            'proofpage_record_context', 'proofpage_replay_context', 'proofpage_check_evidence_run', 'proofpage_affected_outputs',
            'proofpage_business_profiles', 'proofpage_business_context'} <= tool_names, replies
    assert replies[2]['result']['isError'] is False, replies
    print('Copied MCP configuration launches the bundled helper and verifies real tools.')

    # Verify extraction engines/models really ship in the archive, without system Python.
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (900, 160), 'white')
    ImageDraw.Draw(image).text((20, 35), 'Original evidence 12345', font=ImageFont.load_default(size=42), fill='black')
    for suffix, mime in [('png', 'image/png'), ('pdf', 'application/pdf')]:
        original = Path(directory) / ('sample.' + suffix)
        image.save(original)
        extracted = Path(directory) / ('extracted-' + suffix + '.json')
        subprocess.run([entry['command'], '--extract-worker', str(original), str(extracted), mime], check=True, timeout=90)
        result = json.loads(extracted.read_text())
        assert result['status'] == 'complete' and '12345' in result['text'], result
    print('Packaged offline image OCR and scanned-PDF extraction passed.')
