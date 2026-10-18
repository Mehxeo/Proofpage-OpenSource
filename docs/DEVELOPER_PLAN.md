# Developer reliability plan

The first deliverable is a portable record → replay → compare workflow. Existing
workspaces remain compatible; the manifest requires no database migration.

1. Record selected immutable revisions and optional output/quote dependencies.
   Preserve original capture bytes when available and label other representations.
2. Replay validated manifests offline. Allow a caller-supplied SHA-256 pin;
   self-contained hashes detect corruption, not malicious replacement.
3. Compare against current local revisions, report affected outputs and quote
   changes, and fail CI on missing or changed evidence. Refresh is a separate,
   explicit network operation respecting normal collection policies.
4. Expose Python and typed Node SDKs, a CLI, and a reusable GitHub action.
5. Test replay after deleting the workspace, tampering, source drift, dependency
   validation, and real SDK/CLI subprocesses.

Next milestones require customer validation: hosted shared run storage, automatic
collection adapters, PDF region citations, and multimodal training manifests.
Do not claim full browser replay, deterministic model responses, factual truth,
legal permission, or automatic removal of data from trained model weights.

Validation: recruit three teams building research/document agents; integrate one
real regression each. Measure time to diagnose, weekly reuse, and willingness to
pay before expanding hosted infrastructure. No customer outcomes are assumed.


## Implemented in this source increment

- Portable v1 manifests, SHA-256 pins, original representations, exact quote dependencies.
- Offline replay, local comparison, explicit refresh, machine-readable CLI exit codes.
- Python SDK and local Node bridge with TypeScript declarations.
- Composite GitHub action and an offline regression demonstration.
- Ten new Python regression cases and a real Node-to-Python integration test.

The plan above separates this completed developer workflow from customer
research and subsequent hosted/multimodal milestones. Desktop 0.5.0 includes the local evidence and business workflows. The Python and
Node SDKs are distributed in the open-source repository; no registry publication
is claimed.

## Follow-on implementation

- Persisted immutable evidence runs with an additive schema migration.
- Automatic excerpt dependencies when using recorded retrieval; reverse lookup
  from a changed item to affected output IDs.
- Five MCP tools, Python/Node SDK methods, CLI operations, and Agent access UI.
- Exact original bytes for imported image/PDF evidence and external collectors.
- Collector-neutral Python import API with explicit caller-supplied provenance.
- MIT license copied into the local Node SDK; no paid-service requirement.

Remaining: shared self-hosted team collaboration; PDF-region citations; fully
reviewed multimodal training packages; hosted execution; public benchmark and
customer validation. Existing hosted transport can serve the new workspace API,
but this is not yet shared team storage. An optional single-owner OAuth remote MCP
resource server is now available in source; activation requires an authorization
provider and HTTPS hosting. See [connector setup](CONNECTORS.md).
