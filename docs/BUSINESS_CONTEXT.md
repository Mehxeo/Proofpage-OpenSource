# Portable business context

Available in 0.5.0. MIT licensed, local-first, no account, paid service or model API
key required. This feature prepares user-reviewed context; it does not modify
ChatGPT/Claude account memory or train model weights.

## Setup

1. Import selected files using **Import files**. For Google Docs, use the optional [selected-document sync connector](CONNECTORS.md),
   or export to text/PDF and import manually.
2. Open **Business context** and create a profile.
3. Select evidence and classify it as Our business, Customer material, Reference
   material, or Writing example. The picker uses the current library search
   results; search the library first to narrow a large collection.
4. Suggest passages. These are deterministic verbatim passages, not AI-generated
   summaries or inferred preferences. Review conflicting statements yourself.
5. Edit, approve or exclude each suggestion. Approval requires permission and
   review acknowledgments. Detected credential-like content blocks approval.
6. Download the ZIP and inspect it before sharing with an assistant provider.

The ZIP contains BUSINESS.md, INSTRUCTIONS.md, context.json and README.md.
Only approved text and its supporting quotations are included. Original files
and unrelated profile drafts are excluded. Customer/reference content is labeled
separately; it must not be interpreted as your business's products or policies.
Writing examples remain examples, not inferred style instructions.

For bookmarks, export HTML from your browser, preview it in Business context,
and explicitly select entries. Only public-style HTTP(S) URLs without embedded
credentials are accepted; javascript/file URLs are ignored. No page is fetched.
Bookmark records cannot be attached as business evidence. Add a desired URL in
Sources, collect it explicitly, then attach its captured revision.

If a selected source changes, approved context based on the old revision blocks
export/retrieval. Exclude the old passages, attach the current revision and review
new suggestions. Changing a source's role resets its approvals. A context pack
already uploaded elsewhere cannot be remotely revoked by Proofpage.

## Developer interfaces

```python
from proofpage.sdk import Proofpage
p = Proofpage(home='./workspace')
profile = p.create_business('Acme')
p.attach_business_source(profile['id'], 'REVISION_ID', 'business')
draft = p.draft_business(profile['id'])
# Present draft['facts'] to the person reviewing them before calling approval.
fact = draft['facts'][0]
p.review_business_fact(fact['id'], fact['text'], 'approved',
                       permission=True, acknowledge=True)
context = p.business_context(profile['id'])
pack_bytes = p.export_business(profile['id'])
```

Approval flags are explicit assertions by the caller; do not set them on behalf
of a user who has not reviewed the material. MCP intentionally exposes only
profile listing and approved-context retrieval, not approval methods.

```sh
proofpage --home ./workspace business create --name Acme
proofpage --home ./workspace business attach --id PROFILE --revision REVISION --role business
proofpage --home ./workspace business draft --id PROFILE
proofpage --home ./workspace business get --id PROFILE
proofpage --home ./workspace business review --id FACT --text 'Reviewed business statement' --decision approved --permission --acknowledge
proofpage --home ./workspace business export --id PROFILE --path context.zip
proofpage --home ./workspace business bookmarks-preview --path bookmarks.html
proofpage --home ./workspace business bookmarks-import --path bookmarks.html --select 0 --select 2
```

Exports refuse to overwrite files. Errors return JSON and exit code 2. The Python
`proofpage.business` module also exposes bookmark preview/import for integrations.
The authenticated workspace API provides `/api/business`, `/api/business/:id`,
`/api/business/:id/export`, and POST operations `business-create`, `business-attach`,
`business-draft`, `business-review`, `business-training-draft`,
`business-bookmark-preview`, and `business-bookmark-import`. Use the existing
workspace authentication; these are not public unauthenticated endpoints.

MCP: `proofpage_business_profiles` and `proofpage_business_context(profile_id)`.
An assistant can retrieve approved current context without receiving arbitrary
local filesystem access. The text remains untrusted context, not system policy.

## Training

An approved business fact can create an SFT draft using a question you supply.
Use **Draft training example**, or `p.business_training_draft(fact_id, question)`.
The result remains unapproved in Training. Existing rights, role-mapping, review,
and dataset export gates still apply. Customer/reference/writing sources cannot
use this shortcut; create and review any appropriate training examples separately.
Context approval does not establish permission to train a model.

## Limits

Bookmark preview accepts 2 MiB and returns at most 500 distinct entries. Drafting
examines the first 12,000 text characters per source and up to 12 sentence-like
passages, each 15–1,500 characters. It is not exhaustive extraction, a conflict
resolver, a full PII detector, or an automatic description of your business.
Selected file/folder import and watches remain the existing explicit workflows;
there is no silent disk scan. No OAuth connector or destination-account setup
is performed by this feature. Review all quotes, including ones accompanying
edited statements, before sharing.

## Connector update

The source edition now includes an optional selected-document Google Docs sync
connector and OAuth-protected self-hostable remote MCP. See [connector setup](CONNECTORS.md).
The earlier manual-export workflow remains available without OAuth setup. These
connectors require external account configuration and are not activated in the
published desktop downloads.
