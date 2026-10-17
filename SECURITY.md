# Security

Do not place credentials, private source material, or exploit payloads in public issues. Use the repository's private vulnerability reporting channel when the repository is published; if unavailable, contact its maintainer privately before disclosing details. No security contact address is invented by this project.

Local mode is loopback-only and is not a public server. Hosted mode uses authenticated per-user SQLite workspaces, password hashing, expiring sessions, same-origin mutation tokens, scoped/expiring agent keys, request limits, and shared collection budgets. Hosted users cannot select filesystem paths or run browser rendering. Do not expose the legacy local server through a public proxy.

Hosted deployment currently supports one Linux process and one private persistent volume, behind TLS. Logical tenant isolation does not provide separate OS processes per tenant. Protect the host and encrypted backups, monitor disk capacity, restrict outbound network access to public destinations at the infrastructure layer, and keep dependencies current. Recovery codes grant account recovery; treat them as credentials. There is no managed email recovery, MFA, or SSO yet.

Billing is disabled until configured. Validate Checkout, portal, and signed webhook behavior in a separate Stripe sandbox before accepting real payments. Never grant entitlements from a browser success redirect. The configured model provider receives only explicitly submitted evidence; operators must disclose provider and retention practices. Screening is heuristic, not a complete PII or secret detector.
