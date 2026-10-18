# Train from evidence; give existing models evidence tools

## Training workflow

1. Collect a public page, run a bounded crawl, or import a supplied archive.
2. Open evidence and choose **Create training example**. For a conversation with explicit parent links, choose a particular assistant branch; sibling branches and tool outputs are not flattened into the example.
3. Choose a format: supervised messages, preferred/rejected response pairs, prompt/completion corrections, observed tool traces, or evaluation questions. Supply an exact source quote. Preference pairs require a rationale. Human-message examples require the actual participant and explicit context/role approval.
4. Inspect the draft, full evidence, and screening findings in **Training**. Confirm permission and correctness, then approve. Model output and imported branches are never automatically approved. Editing creates another draft linked to the prior example.
5. Select approved examples of one format and freeze a dataset. Download its ZIP bundle. It includes trainer payloads, source citations/hashes, a manifest, grouped train/validation/test partitions, and `validate.py`.
6. Unzip and run `python validate.py` before using the data. Revoking either source permission or an example's approval blocks future managed exports. Previously downloaded files cannot be recalled.

Payload formats:

| Format | JSONL shape | Intended use |
|---|---|---|
| Supervised | `{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}` | Conversational SFT |
| Preference | `{"prompt":"...","chosen":"...","rejected":"..."}` | DPO/preference training |
| Correction | `{"prompt":"...","completion":"..."}` | Prompt/completion SFT |
| Evaluation | `{"prompt":"...","reference":"..."}` | Held-out evaluation; all records in test |
| Trace | `{"events":[...]}` | Actual observed calls/results; adapt to your trainer's tool schema |

SFT and preference shapes follow the primary [TRL dataset formats](https://huggingface.co/docs/trl/dataset_formats), [SFT trainer](https://huggingface.co/docs/trl/sft_trainer), and [DPO trainer](https://huggingface.co/docs/trl/dpo_trainer) documentation. Load `train.jsonl` with your trainer's JSON dataset loader and its selected model/tokenizer. Proofpage prepares data; it does not provision GPUs, download a training model, or launch paid training jobs.

Exact payload duplicates are removed. Source groups and near duplicates (0.85 Jaccard similarity of word five-grams) remain together. Assignment is deterministic within the dataset; at least one group is allocated to train unless the format is evaluation. Small bundles can have empty validation/test partitions. Splits are not a global registry: across independently frozen datasets, check source overlap yourself and keep evaluation sources out of training. Heuristic screening catches common credentials, emails, phone numbers, and instruction-like text; it is not comprehensive anonymization or a factual verifier. The original evidence stays unchanged when a draft is redacted.

## Existing models through MCP

Configure your MCP-capable assistant with the command in README. Eighteen tools support source inspection, collection, cited retrieval, freshness checks, durable bounded crawls, extraction submissions, and training drafts. No approval/export tool is exposed. Configure source URLs in Proofpage first.

Typical sequence:

1. `proofpage_list_sources`
2. `proofpage_ensure_fresh` with `source_id` and `max_age_seconds`
3. `proofpage_get_context` with `query`
4. Answer with the returned citation IDs, or submit a grounded draft through `proofpage_draft_example`.

For multiple pages: `proofpage_start_crawl`, `proofpage_step_crawl`, `proofpage_get_crawl`, and optionally `proofpage_cancel_crawl`. The web server advances jobs automatically; a standalone stdio client must call step. Respect `next_attempt`; do not loop through cooldowns. Collection stays on the starting origin and directory, up to 20 pages/depth 3. HTML links (including pagination links), sitemap/XML/RSS links are discovered. A feed is a discovery source, not inferred article content. Jobs survive restart; individual failures remain visible. Restore cancels pending crawls. Cancellation stops future requests; an in-flight request may finish.

`python examples/agent_client.py --home .proofpage "your search"` demonstrates a real subprocess handshake and cited context request. Recorded successful collection/context/freshness calls can become observed-trace drafts. Internal reasoning is never inferred or fabricated.

## Use a local or hosted model in the workbench

Before starting the server:

```sh
export PROOFPAGE_MODEL_URL=http://127.0.0.1:11434/v1
export PROOFPAGE_MODEL_NAME=your-installed-model
# Hosted endpoints can additionally use PROOFPAGE_MODEL_KEY.
python3 -m proofpage --home .proofpage serve
```

Use an OpenAI-compatible `/v1` base URL supporting chat completions and JSON output. Ollama documents [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility). Proofpage does not install or pull an LLM. Remote endpoints require HTTPS; redirects are refused. Credentials stay in the server environment and are not shown in the UI.

**Draft with my model** sends up to 20,000 characters of selected evidence only after the explicit send action. Detected credentials block transmission. Review personal data before sending to a hosted provider. **New extraction recipe** defines fields; **Extract with my model** requires exact source quotes for non-null values. Missing fields are null. An exact quote does not prove the model interpreted it correctly. Results remain unreviewed.

## Optional offline JavaScript rendering

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[render]'
.venv/bin/python -m playwright install chromium
.venv/bin/python -m proofpage --home .proofpage serve
```

Enable rendering in a crawl. Chromium executes captured inline JavaScript with external resources, network calls, service workers, and WebSockets blocked. Original HTML is retained in provenance. Pages requiring external scripts or API data remain incomplete; this is deliberately not a general authenticated browser crawler. Each capture records blocked-request coverage. Missing Chromium produces a failed run, never a successful capture.

## Connect by copying a prompt

In the local workspace, open **Agent access → Copy setup prompt**, then paste it into an MCP-capable AI assistant. The prompt includes the actual executable and workspace paths. **Copy MCP configuration** provides the raw JSON instead. If clipboard access is denied, Proofpage displays selectable text for manual copying.

Desktop downloads include a separate console MCP helper, so the assistant does not need a system Python installation. Keep the app's support files together and recopy settings after moving the app. The assistant must support local stdio MCP and be permitted to configure integrations; a prompt cannot add support to clients that lack it. It should preserve existing configuration and verify the connection with `proofpage_list_sources`. A normal web-chat model may only be able to explain the setup.

The prompt contains local filesystem paths, but no API keys or session token. Hosted users should create scoped keys in Account and configure them through the client's secure credential settings, never paste secrets into a prompt.

## Evidence tools (development branch)

Rights, history and receipts: `proofpage_get_rights`, `proofpage_diff_revisions`, `proofpage_list_changes_since`, `proofpage_get_receipt`.

Quote checks: `proofpage_check_answer`, `proofpage_verify_quotes`, `proofpage_get_quote_check`, `proofpage_step_quote_check`, `proofpage_cancel_quote_check`. [Schemas and consent](VERIFY.md). Mechanical matches and model-written reviews never approve training data.
