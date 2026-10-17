# Open-source and hosted Proofpage

All application code, including the hosted edition, is MIT licensed. Anyone can run, modify, or host it. The software does not require a Proofpage account, license server, or subscription in local mode. Models/weights are not included; connect a model with its own applicable license.

The hosted service sells managed storage, collection capacity, scheduling, and configured model assistance. Dataset review and export use the same core implementation as local mode. Customer evidence is not automatically used to train a shared model. The operator controls the server and optional model endpoint and must disclose those practices to customers.

## Run locally without an account

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m proofpage --home .proofpage serve
```

Open `http://127.0.0.1:8765`. There is no hosted account quota in local mode; collection still respects destination budgets and robots policies. Use the local server only on loopback.

## Run a hosted development instance

```sh
.venv/bin/python -m pip install -e '.[hosted,test]'
export PROOFPAGE_PUBLIC_URL=http://127.0.0.1:8000
export PROOFPAGE_DEVELOPMENT=true
.venv/bin/python -m proofpage --home .proofpage-hosted hosted
```

In another terminal create a seven-day, one-use invitation bound to the intended email:

```sh
.venv/bin/python -m proofpage --home .proofpage-hosted invite you@example.com
```

Open `/login`, choose Accept invitation, enter the code, and create a 12–256 character password. Store the recovery code privately. Recovery replaces the password and recovery code and revokes all old sessions/agent keys. Invitations are delivered manually; there is no invented or unconfigured email sender. Do not use development mode on a public network.

## Deploy on your server

1. Point your hostname at a Linux server with Docker Compose and ports 80/443 available.
2. Copy `.env.example` to `.env`, set the real domain and HTTPS origin. Keep development mode unset.
3. Run `docker compose up --build -d`. Caddy terminates TLS; the application port is internal. A non-root container owns the persistent data volume.
4. Run `docker compose exec proofpage python -m proofpage invite person@example.com`, and deliver that invitation through your existing trusted channel.
5. Check `/healthz`, sign in, import a synthetic file, and verify a dataset export before inviting customers.

The [FastAPI container guidance](https://fastapi.tiangolo.com/deployment/docker/) informed the container entry point. This release supports one Linux process and one data volume, not a horizontally scaled cluster or serverless ephemeral filesystem. A process lock rejects multiple workers on one volume. Keep workspace data on a local durable filesystem, not NFS. Each account has a separate SQLite database. This is logical tenant separation, not separate containers per user.

Caddy forwards requests but the app deliberately does not trust arbitrary forwarded identity headers. Auth IP limits therefore aggregate behind the proxy, with additional per-email limits. If operating at higher traffic, add a trusted edge rate limiter and an explicitly configured trusted proxy policy before expanding registration. Registration is invitation-only.

The Dockerfile/Compose configuration is supplied; local validation could not run a container because the current machine's Docker daemon was unavailable. CI includes a Linux image build. CI has not run on a public repository yet.

## Configure subscriptions

Billing is disabled until the key, recurring price, and webhook secret are configured. There is no hard-coded monetary price. The Account page retrieves the actual configured Stripe Price and Checkout uses that same ID.

Use a dedicated Stripe sandbox first. Configure:

- `PROOFPAGE_STRIPE_KEY`: preferably a restricted key with the necessary Customer, Checkout, Subscription, Price, and Billing Portal access.
- `PROOFPAGE_STRIPE_PRICE_ID`: active flat recurring Price for Pro.
- `PROOFPAGE_STRIPE_WEBHOOK_SECRET`: signing secret for `/webhooks/stripe`.
- `PROOFPAGE_STRIPE_LIVE=false` for sandbox; change to true only with matching live resources.

Enable the Customer Portal's payment-method and cancellation features in Stripe. Configure snapshot webhook events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Match API version `2026-08-26.dahlia`. Follow [Stripe subscription guidance](https://docs.stripe.com/billing/subscriptions/build-subscriptions) and [webhook delivery/signature requirements](https://docs.stripe.com/webhooks).

Signed webhooks fetch current subscription state; event metadata and arrival order do not determine entitlement. A checkout success URL never grants access. Duplicate events are ignored only after successful processing, so failures can retry. Active/trialing subscriptions with the configured price and unexpired billing period grant Pro. Past-due/unpaid/canceled states revert to Free. A cancellation at period end retains access until the active period ends. Missed deliveries are reconciled hourly while the server runs, or through Refresh billing status. Open Checkout sessions are reused to avoid duplicate purchases. Customer creation and Checkout retries use durable idempotency keys.

Taxes are not automatically enabled. The actual Stripe sandbox/live configuration, tax obligations, domain, terms, support contact, and privacy policy are operator setup, not fabricated defaults. No real Stripe account was modified and no live charge was made during implementation. Automated tests exercise actual SDK webhook signature parsing with synthetic events and mock provider responses. A real sandbox purchase/renewal/failure/cancellation cycle remains required before launch.

## Allowances and behavior

| Hosted allowance per UTC month | Free | Pro |
|---|---:|---:|
| Collection attempts | 100 | 5,000 |
| Operator-model requests | 0 | 100 |
| Workspace write requests | 2,000 | 50,000 |
| SQLite workspace storage | 100 MiB | 1 GiB |

These are initial service defaults in `proofpage/accounts.py`, not a promised commercial price. Quota reservation is transactional. Failed attempts can count; no overage charges are generated. Quotas do not remove existing evidence or block reading/export on downgrade. Storage uses SQLite page limits; existing larger databases remain readable after downgrade. Collection budgets and cooldowns also apply globally per destination across hosted tenants. Each request is bounded to 16 MiB, and original archive limits still apply.

Hosted users cannot configure filesystem folder watches, arbitrary data directories, browser rendering, or their own server-side secret environment. Upload archives from the browser. Scheduled public collection and crawl steps consume the same allowance as direct requests. Endpoint model assistance requires explicit sending and the Pro allowance. Local mode retains folder watches, your own model configuration, and optional offline rendering.

## Connect assistants

Create an Account agent key with either read-only scope or collection/draft scope. Keys expire after 90 days, are stored only as hashes, and can be revoked. Neither scope allows approving or exporting datasets. Configure an MCP client to run `python3 -m proofpage remote-mcp` with these environment variables:

```text
PROOFPAGE_REMOTE_URL=https://your-domain.example
PROOFPAGE_AGENT_KEY=the-key-shown-once
```

The shipped stdio bridge calls the authenticated `/agent` JSON-RPC endpoint. The bridge is the supported client path; the endpoint is not advertised as a complete Streamable HTTP MCP transport with OAuth/SSE. Remote redirects are refused to prevent credential forwarding.

## Ownership, backups, and operations

Account → Download workspace backup exports evidence, revisions, and datasets without hosted credentials or billing records. Restore it on your own machine:

```sh
python3 -m proofpage restore downloaded-workspace.sqlite3 ./restored-workspace
python3 -m proofpage --home ./restored-workspace serve
```

Restore pauses local automation. Keep hosted volume backups encrypted and access-controlled. For a full service backup, stop the service briefly and snapshot the entire persistent volume, including the account database and workspace databases; a workspace export alone does not include account or billing state. Restore full volumes offline before restarting a single application process. Periodically test recovery.

Monitor health, volume capacity, failed provider requests, webhook delivery, and `audit` action records (no source bodies/passwords). The authenticated `/api/account/audit` exposes the current account's last 100 actions. Streaming workspace backups use temporary files under the private `exports` directory and remove them when downloads finish; remove abandoned files after a process crash. Never publicly serve the volume. Event/audit metadata retention and account deletion should be set by the operator before a broad public launch. This release has no automatic data-retention deletion, SSO/MFA, email recovery, team roles, or multi-node coordination.
