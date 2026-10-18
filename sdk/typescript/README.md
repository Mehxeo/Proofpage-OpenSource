# Proofpage local SDK

MIT licensed; no hosted account required. Import `Proofpage` from `index.js`.
Requires Node 18+ and Python 3.11+ with this Proofpage source installed. This is
a typed subprocess bridge, not a remote service client. Pass `python` and `home`
in the constructor to choose the engine and workspace.

See `../../docs/DEVELOPER_WORKFLOW.md` for recording/replay, persistent runs,
CI checks, cancellation and limits. `../../docs/EVIDENCE_FORMAT.md` describes
the portable format. Run `node --test test.mjs` from this folder after installing
Proofpage; set `PROOFPAGE_TEST_PYTHON` to choose your interpreter.

The package is marked private to prevent accidental registry publication. That
flag does not change the MIT license or restrict copying, modifications, use,
redistribution, self-hosting, or commercial use under that license.
