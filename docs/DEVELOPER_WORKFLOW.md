# Reproducible evidence for developers

Desktop 0.5.0 includes the saved-input UI and MCP tools. For CLI and SDK use, install
this checkout with `python -m pip install -e .`. Python 3.11+ is required.

## Record and replay

```python
from proofpage.sdk import Proofpage

client = Proofpage(home='./evidence-workspace')
captured = client.capture('https://example.com')  # explicit network operation
if captured['collection']['state'] != 'available':
    raise RuntimeError(captured['collection'])
manifest = client.record(captured['revision_ids'], name='research-answer-1')
pin = client.write(manifest, 'inputs.json')  # refuses to overwrite
saved = Proofpage.replay('inputs.json', expected_sha256=pin)  # no workspace/network
text_for_model = saved['records'][0]['text']
```

Replay supplies the exact recorded text and stored original representations. It
is not browser interaction replay or a promise of identical model answers.
HTTP originals are labeled exact or reconstructed; supplied revision raw data
is explicitly labeled `stored_raw_utf8`. OCR/extractor metadata is preserved
as stored; older records may lack extractor versions. There is no automatic
interception of model or browser calls. Record the revisions actually used.

## Trace outputs to exact quotations

Pass `dependencies` to `client.record`:

```python
revision = captured['revision_ids'][0]
# Offsets are Python Unicode character indices, not UTF-16 offsets.
dependencies = [{
    'output_id': 'answer-1', 'revision_id': revision,
    'start': 0, 'end': 7, 'quote': text_for_model[:7]
}]
manifest = client.record([revision], dependencies=dependencies)
report = client.check(manifest)
```

Quotes must exactly match a nonempty slice. Compare returns changed/missing
records, lexical differences, affected output IDs, and whether each quote still
occurs in the current text. It checks the **local workspace**, not the live web.
`client.refresh(manifest)` explicitly fetches original public targets through
normal collection restrictions/budgets, then compares. Blocked/deferred results
are reported; old evidence is not silently treated as a successful refresh.
A changed source marks an output for review; it does not prove the output false.

## CLI and CI

```sh
proofpage --home ./evidence-workspace evidence record inputs.json --revision REVISION_ID
proofpage evidence replay inputs.json --sha256 TRUSTED_MANIFEST_SHA256
proofpage --home ./evidence-workspace evidence check inputs.json --sha256 TRUSTED_MANIFEST_SHA256
proofpage --home ./evidence-workspace evidence refresh inputs.json
```

Use `--dependencies dependencies.json` when recording. Commands return JSON.
Exit codes: 0 successful; 1 drift/missing evidence or unsuccessful refresh;
2 malformed inputs, failed checksum, or file errors. Replay does not create a
workspace. Check requires the original workspace (or its backup) for current
revision comparison. A fresh workspace reports missing evidence.

The reusable composite action lives at `.github/actions/evidence-check`:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: '3.13'
- run: python -m pip install -e .
- uses: ./.github/actions/evidence-check
  with:
    manifest: fixtures/inputs.json
    sha256: YOUR_REVIEWED_MANIFEST_HASH
    # home: restored-workspace  # optional current-revision comparison
```

This example runs inside a checkout containing Proofpage. External projects
should check out a reviewed Proofpage commit separately, install that path, and
reference its action directory. Pin the commit; do not install an unrelated
same-name registry package. Upload `proofpage-evidence-report.json` with
`if: always()` if you need drift reports as CI artifacts. Offline-only mode
validates integrity; it does not claim freshness. No automatic network refresh.
Keep the trusted checksum in reviewed configuration separate from untrusted
manifest updates. Hashes establish integrity relative to a trusted pin, not
publisher identity. Manifests contain source content and may contain sensitive
material; review before committing them to a public repository.

## Node and TypeScript

The local SDK is in `sdk/typescript` (not published to npm):

```js
import { Proofpage } from './sdk/typescript/index.js';
const client = new Proofpage({ python: '/path/to/venv/bin/python', home: './evidence-workspace' });
const saved = await client.record('inputs.json', { revisions: ['REVISION_ID'] });
const replay = await client.replay('inputs.json', { sha256: saved.sha256 });
const report = await client.check('inputs.json');
if (!report.ok) process.exitCode = 1;
```

This SDK launches the local CLI without a shell and includes TypeScript types,
a 30-second default timeout and AbortSignal cancellation. Set `timeoutMs` higher
for explicit refreshes. Drift resolves to a report; malformed inputs reject.
The Python engine must be installed. This is not a hosted HTTP SDK, and no
automatic retries are performed for mutations.

## Current boundaries

Manifests are capped at 64 MiB, include base64 originals, and are not encrypted
or signed. Existing separately signed proof bundles remain available. Dependency
tracking is explicit, per manifest; dependencies are recorded through explicit SDK/MCP retrieval, not arbitrary model interception.
There is no shared team service, PDF-region UI, or new training exporter in this increment.
See DEVELOPER_PLAN.md for the roadmap and customer-validation milestones.

## Try the regression demo

Run `python examples/evidence_regression.py` from this checkout after installing
it. The offline fixture changes a price, identifies the affected answer, and
asserts that replay still supplies the original price. It uses a temporary
workspace and leaves your library untouched. This example also runs in CI.


## Persistent agent runs and reverse dependencies

Everything here is MIT licensed and runs locally. No subscription or vendor API
key is needed. The additive database migration preserves existing workspaces.

```python
client = Proofpage(home='./evidence-workspace')
retrieval = client.record_context('pricing', output_id='answer-42', name='Pricing research')
if retrieval['recording']:
    run_id = retrieval['recording']['run_id']
    pinned = client.replay_context(run_id)
    comparison = client.check_run(run_id)
    client.export_run(run_id, 'answer-42-inputs.json')
```

The dependency means the excerpt was supplied to an output, not that a model
actually used it. Saved runs are immutable. Recording again creates another
run, even with the same output ID. `client.affected_outputs(item_id)` finds
recorded output dependencies whose source revisions differ from the current
library. Missing records are included. Checks do not perform network requests.

In the app: Agent access → enter a query and an Output ID → Retrieve context.
Use Recorded agent inputs → Load saved runs → Replay / Check / Export.

CLI:

```sh
proofpage --home ./evidence-workspace evidence-run record-context --query pricing --output-id answer-42
proofpage --home ./evidence-workspace evidence-run list
proofpage --home ./evidence-workspace evidence-run replay RUN_ID
proofpage --home ./evidence-workspace evidence-run check RUN_ID
proofpage --home ./evidence-workspace evidence-run affected ITEM_ID
proofpage --home ./evidence-workspace evidence-run export RUN_ID --output inputs.json
```

Node exposes `recordContext`, `listRuns`, `replayRun`, `checkRun`,
`affectedOutputs`, and `exportRun`. MCP exposes `proofpage_record_context`,
`proofpage_replay_context`, `proofpage_check_evidence_run`,
`proofpage_list_evidence_runs`, and `proofpage_affected_outputs`.
MCP returns bounded recorded excerpts; exporting large originals remains an
explicit app/CLI/SDK action. No filesystem paths are accepted by these MCP tools.

## Bring your own collector

Use `client.import_capture(url, text=extracted_text, original=original_bytes,
content_type='text/html', collector='your-collector/version')` to record output
from Playwright, Firecrawl, or your own collector. This method does not call
those services or fetch the URL. Supply the bytes your collector actually
returned. For Playwright's rendered HTML, encode `await page.content()` as
UTF-8; do not describe it as the original HTTP response. For a provider's
Markdown output, use `text/markdown` and the returned Markdown bytes.

Imports are explicitly caller-supplied, cannot obtain HTTP receipts retroactively,
and preserve collector metadata. Capture policies and permissions remain the
caller's responsibility. The same revision can feed `record`, training review,
or context retrieval. Each text/original is limited to 8 MiB.
