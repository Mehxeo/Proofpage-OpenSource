# Contributing to Proofpage

Proofpage is MIT licensed, including the hosted server. Local use requires no license server, subscription, or account. Hosted subscriptions pay for operated infrastructure and configured allowances.

Use Python 3.11+ with SQLite FTS5. Create a virtual environment and install `pip install -e '.[hosted,test]'`. Run `python -m unittest discover -s tests -v` and `node --check` on changed JavaScript. For optional offline rendering, install `.[render]` and Chromium separately.

Preserve original evidence, explicit review, source permission, and truthful access/coverage. Never turn a challenge page into successful evidence, infer missing conversation roles, log credentials, or bypass shared provider limits. Add tests for changes to authentication, tenant scope, billing, collection limits, dataset integrity, or migrations. Use synthetic fixtures, not real account exports.

Submit focused changes with the problem, resulting behavior, and verification. Contributions are under MIT. No contributor license agreement is required. Do not commit data directories, `.env`, credentials, or generated distributions. New dependencies must have compatible redistribution terms; model weights have their own licenses and are not bundled here.
