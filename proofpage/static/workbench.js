// Training workbench and agent access views, plus the dialogs they open.
let workState, trainingFilter = 'all';
const kinds = {sft: 'Supervised conversations', preference: 'Preference pairs', correction: 'Corrections', trace: 'Observed tool traces', evaluation: 'Evaluation questions'};
const EXAMPLE_ICONS = {sft: 'message', preference: 'layers', correction: 'refresh', trace: 'plug', evaluation: 'check'};

function originLabel(origin) {
  if (origin === 'manual') return 'Written by you';
  if (origin === 'external_agent') return 'Drafted by a connected agent';
  if (origin === 'source_branch') return 'From a supplied conversation branch';
  if (String(origin).startsWith('model:')) return 'Drafted by ' + origin.slice(6);
  return String(origin || 'Unknown origin').replaceAll('_', ' ');
}

function workDialog(title, html) { openModal(title, html); }
function options(rows, value = 'id', label = 'name') { return rows.map(row => `<option value="${escape(row[value])}">${escape(row[label])}</option>`).join(''); }

async function renderWorkbench(selected) {
  workState = await api('workbench');
  if (selected === 'training') renderTraining();
  else await renderAgents();
}

// ---------- Training ----------
function candidateRow(candidate) {
  const warnings = JSON.parse(candidate.findings || '[]').length;
  return `<div class="candidate">
    <span class="kind-icon" aria-hidden="true">${icon(EXAMPLE_ICONS[candidate.kind] || 'file')}</span>
    <div><h3>${escape(kinds[candidate.kind] || candidate.kind)} ${statusPill(candidate.status)}${warnings ? `<span class="pill tone-warn" title="Heuristic screening findings">${pluralize(warnings, 'finding')}</span>` : ''}</h3>
      <p>${escape(originLabel(candidate.origin))} · ${escape(relativeTime(candidate.created_at))}${candidate.notes ? ' · ' + escape(candidate.notes.slice(0, 150)) : ''}</p></div>
    <div class="actions">${candidate.status === 'approved' ? `<label class="check-inline"><input name="freeze-candidate" type="checkbox" value="${escape(candidate.id)}"> Include</label>` : ''}<button type="button" class="secondary small" data-candidate="${escape(candidate.id)}">${icon('eye')}Inspect & review</button></div>
  </div>`;
}

function renderTraining() {
  setHeading('Training', 'Evidence into training data.', 'Draft, inspect, approve, and export examples — each one tied to an exact source quote.');
  const candidates = workState.candidates;
  const counts = candidates.reduce((total, c) => ({...total, [c.status]: (total[c.status] || 0) + 1}), {});
  const tabs = [['all', 'All', candidates.length], ['draft', 'Drafts', counts.draft || 0], ['approved', 'Approved', counts.approved || 0], ['rejected', 'Rejected', counts.rejected || 0], ['revoked', 'Revoked', counts.revoked || 0]]
    .filter(([id, , count]) => count || ['all', 'draft', 'approved'].includes(id));
  if (!tabs.some(([id]) => id === trainingFilter)) trainingFilter = 'all';
  const shown = candidates.filter(c => trainingFilter === 'all' || c.status === trainingFilter);
  const approved = counts.approved || 0;

  $('content').innerHTML = `
    <div class="toolbar"><div class="actions">
      <button type="button" id="new-example" class="primary">${icon('plus')}New example</button>
      <button type="button" id="new-recipe" class="secondary">${icon('list')}New extraction recipe</button>
      <button type="button" id="extract-model">${icon('sparkle')}Extract with my model</button>
    </div></div>
    <p class="callout">${icon('shield')}<span>Examples remain drafts until you review correctness, source permission, and screening findings. Editing creates a new version; nothing is approved automatically.</span></p>
    <div class="tabs" role="group" aria-label="Filter examples">${tabs.map(([id, label, count]) => `<button type="button" data-training-filter="${id}" aria-pressed="${trainingFilter === id}">${label} <span class="count">${count}</span></button>`).join('')}</div>
    ${shown.length ? shown.map(candidateRow).join('')
      : candidates.length ? `<p class="muted">No examples in this group.</p>`
        : empty('No examples yet.', 'Open a record in your library and choose “Create training example”, or start one here from your newest evidence.', `<button type="button" class="primary" data-go="library">${icon('library')}Choose evidence</button>`, 'training')}
    ${approved ? `<form id="training-freeze" class="freeze-bar">
      <h3>${icon('layers')}<span id="freeze-count">0</span>&nbsp;selected</h3>
      <input name="name" required placeholder="Dataset name" aria-label="Dataset name">
      <select name="kind" aria-label="Example format">${Object.entries(kinds).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select>
      <button class="primary">Freeze dataset</button>
    </form>
    <p class="muted">Tick “Include” on approved examples. One format per bundle. Sources and near duplicates stay in the same split; small datasets can have empty splits.</p>` : ''}
    <div class="section-label">Training bundles · ${workState.datasets.length}</div>
    ${workState.datasets.length ? `<div class="cards">${workState.datasets.map(dataset => `<article class="card dataset-card">
      <div class="card-top"><span class="tag">${icon(EXAMPLE_ICONS[dataset.format] || 'file')}${escape(kinds[dataset.format] || dataset.format)}</span>${seal(dataset.hash, 'Bundle SHA-256')}</div>
      <h3>${escape(dataset.name)}</h3>
      <p>${pluralize(JSON.parse(dataset.manifest).records.length, 'example')} with source manifests, checksums, and a standalone validator.</p>
      <div class="card-meta"><span title="${escape(date(dataset.created_at))}">${icon('clock')}Frozen ${escape(relativeTime(dataset.created_at))}</span><button type="button" class="secondary small" data-bundle="${escape(dataset.id)}">${icon('download')}Download bundle</button></div>
    </article>`).join('')}</div>` : '<p class="muted">Frozen training bundles appear here. Each is reproducible and re-checks revocations on download.</p>'}
    ${workState.extractions.length ? `<div class="section-label">Structured extractions · unreviewed</div>${workState.extractions.map(extraction => `<details><summary>${escape(workState.recipes.find(recipe => recipe.id === extraction.recipe_id)?.name || 'Extraction')} · ${escape(originLabel(extraction.origin))} · ${escape(relativeTime(extraction.created_at))}</summary><pre>${escape(JSON.stringify(JSON.parse(extraction.result), null, 2))}</pre></details>`).join('')}` : ''}`;

  $('new-example').onclick = () => action(() => openExample());
  $('new-recipe').onclick = openRecipe;
  $('extract-model').onclick = () => action(() => openModel(null, 'extraction'));
  if ($('training-freeze')) {
    const updateCount = () => { $('freeze-count').textContent = document.querySelectorAll('[name=freeze-candidate]:checked').length; };
    $('content').onchange = event => { if (event.target.name === 'freeze-candidate') updateCount(); };
    $('training-freeze').onsubmit = event => {
      event.preventDefault();
      const form = new FormData(event.target);
      action(async () => {
        const result = await api('training-freeze', {name: form.get('name'), kind: form.get('kind'), candidate_ids: [...document.querySelectorAll('[name=freeze-candidate]:checked')].map(input => input.value)});
        notice(`Frozen ${pluralize(result.records, 'example')}. Splits: ${Object.entries(result.splits || {}).map(([split, count]) => split + ' ' + count).join(', ')}`);
        await refresh();
      }, event.submitter);
    };
  }
}

// ---------- Agent access ----------
async function renderAgents() {
  setHeading('Agent access', 'Give your models reliable evidence.', 'Cited context, bounded collection, and optional help from your own model. Approval and export stay with you.');
  const tools = workState.tools || [];
  const webSources = state.sources.filter(source => source.kind === 'web');
  $('content').innerHTML = `
    <section class="panel" id="connect-panel">
      <div class="panel-head"><div><h3>Connect your AI assistant</h3><p>Copy a setup prompt and paste it into an MCP-capable assistant. It contains the exact connection settings for this workspace.</p></div>${tools.length ? `<span class="pill tone-accent">${pluralize(tools.length, 'MCP tool')}</span>` : ''}</div>
      <ol class="setup-steps">
        <li><b>Copy the setup prompt</b><span>It includes this computer’s executable and data-folder paths.</span></li>
        <li><b>Paste it into your assistant</b><span>It asks the assistant to keep existing integrations and add Proofpage.</span></li>
        <li><b>Let it verify</b><span>The assistant lists your sources to confirm the connection.</span></li>
      </ol>
      <div class="actions"><button type="button" class="primary" id="copy-mcp-prompt">${icon('copy')}Copy setup prompt</button><button type="button" class="secondary" id="copy-mcp-config">${icon('copy')}Copy MCP configuration</button></div>
      <p id="mcp-copy-status" class="copy-status" role="status"></p>
      <details><summary>Connection settings and manual setup</summary><textarea id="mcp-setup-text" readonly aria-label="MCP setup text" rows="10" class="mono"></textarea></details>
      ${tools.length ? `<details><summary>What your assistant can do</summary><ul class="tool-list">${tools.map(tool => `<li><code>${escape(tool.name)}</code>${escape(tool.description)}</li>`).join('')}</ul></details>` : ''}
      <p class="muted">Your assistant needs support for local MCP tools and permission to configure them. Settings contain local paths; copy them only to an assistant you trust. Collection and draft tools are available; approval and export stay in Proofpage.</p>
    </section>
    <div class="grid-2">
      <form id="context-form" class="panel">
        <h3>Try cited context</h3>
        <p>See exactly what an assistant receives: bounded excerpts with stable citation IDs.</p>
        <div class="searchbox">${icon('search')}<input name="query" required placeholder="Search your evidence" aria-label="Context query"></div>
        <div class="actions"><button class="secondary">${icon('quote')}Retrieve context</button></div>
      </form>
      <section class="panel">
        <h3>Your model</h3>
        <p>${escape(workState.model.detail)}</p>
        ${workState.model.configured ? `<p><span class="pill tone-ok">Configured</span> <code>${escape(workState.model.model)}</code> · ${escape(workState.model.url)}</p>`
          : '<pre>PROOFPAGE_MODEL_URL=http://127.0.0.1:11434/v1\nPROOFPAGE_MODEL_NAME=your-installed-model\n# Optional hosted credential: PROOFPAGE_MODEL_KEY</pre><p class="muted">Set these environment variables before starting Proofpage. Evidence is only sent when you ask.</p>'}
      </section>
    </div>
    <div id="context-results"></div>
    <div class="section-label">Bounded collection jobs · ${workState.jobs.length}</div>
    <div class="toolbar"><div class="actions"><button type="button" id="new-crawl" class="primary">${icon('layers')}Collect multiple pages</button><button type="button" id="jobs-refresh">${icon('refresh')}Refresh results</button></div></div>
    ${workState.jobs.length ? `<div class="rows">${workState.jobs.map(job => `<div class="row"><div><h3>${escape(state.sources.find(source => source.id === job.source_id)?.name || 'Source')}</h3><p>${escape(job.detail || 'Waiting to start.')} · updated ${escape(relativeTime(job.updated_at))}</p></div><div class="actions">${statusPill(job.state)}<button type="button" class="small" data-job="${escape(job.id)}">Page outcomes</button>${['queued', 'running'].includes(job.state) ? `<button type="button" class="small danger-text" data-cancel-job="${escape(job.id)}">Cancel</button>` : ''}</div></div>`).join('')}</div>`
      : '<p class="muted">Crawl a few pages within one site directory. Robots rules, cooldowns, and daily budgets apply to every request.</p>'}
    <form id="fresh-form" class="panel">
      <h3>Refresh stale evidence</h3>
      <p>Recheck a public source only if its newest capture is older than the age you choose. Shared cooldowns still apply; archives are never called fresh.</p>
      ${webSources.length ? `<div class="grid-2"><label>Source<select name="source_id">${options(webSources)}</select></label><label>Maximum age in seconds<input type="number" name="max_age_seconds" value="86400" min="60"></label></div><div class="actions"><button class="secondary">${icon('refresh')}Check freshness</button></div>`
        : '<p class="muted">Add a web source to use freshness checks.</p>'}
    </form>`;

  $('new-crawl').onclick = () => action(openCrawl);
  $('jobs-refresh').onclick = () => action(refresh, $('jobs-refresh'));
  if (hostingMode === 'local') {
    const connection = await api('mcp-setup');
    $('mcp-setup-text').value = JSON.stringify(connection.config, null, 2);
    const copyConnection = async text => {
      $('mcp-setup-text').value = text;
      try {
        await navigator.clipboard.writeText(text);
        $('mcp-copy-status').textContent = 'Copied. Paste it into your AI assistant.';
      } catch {
        $('mcp-setup-text').closest('details').open = true;
        $('mcp-setup-text').focus();
        $('mcp-setup-text').select();
        $('mcp-copy-status').textContent = 'Select and copy the text below; clipboard access is unavailable.';
      }
    };
    $('copy-mcp-prompt').onclick = () => copyConnection(connection.prompt);
    $('copy-mcp-config').onclick = () => copyConnection(JSON.stringify(connection.config, null, 2));
  } else {
    $('copy-mcp-prompt').disabled = true;
    $('copy-mcp-config').disabled = true;
    $('mcp-copy-status').textContent = 'For hosted access, create a scoped key in Account and follow the hosted connection guide. Never paste that key into a prompt.';
  }
  $('context-form').onsubmit = event => {
    event.preventDefault();
    const text = new FormData(event.target).get('query');
    action(async () => {
      const result = await api('context', {query: text});
      const terms = text.toLowerCase().split(/\s+/);
      $('context-results').innerHTML = result.excerpts.length
        ? `<div class="section-label">Cited context · ${pluralize(result.excerpts.length, 'excerpt')} · ${result.characters} characters</div>
          <p class="muted">${escape(result.coverage)} ${escape(result.instruction)}</p>
          ${result.excerpts.map(excerpt => `<article class="citation">
            <div class="card-top"><h3>${escape(excerpt.title)}</h3><button type="button" class="small" data-item="${escape(excerpt.item_id)}">${icon('eye')}Open evidence</button></div>
            <blockquote>${highlight(excerpt.text.length > 700 ? excerpt.text.slice(0, 700) + '…' : excerpt.text, terms)}</blockquote>
            <div class="card-meta"><button type="button" class="small" data-copy="${escape(excerpt.citation_id)}" title="Copy citation ID">${icon('copy')}<code>${escape(excerpt.citation_id.slice(0, 36))}…</code></button><span>${icon('clock')}Captured ${escape(relativeTime(excerpt.captured_at))}</span><span>Characters ${excerpt.start}–${excerpt.end}</span></div>
          </article>`).join('')}
          <details><summary>Raw response an agent receives</summary><pre>${escape(JSON.stringify(result, null, 2))}</pre></details>`
        : empty('No cited context found.', 'Lexical search found no matching excerpts. Try words that appear in your evidence.', '', 'search');
    }, event.submitter);
  };
  $('fresh-form').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target);
    action(async () => {
      const result = await api('freshness', {source_id: form.get('source_id'), max_age_seconds: Number(form.get('max_age_seconds'))});
      notice(result.detail || ('Freshness: ' + (result.state || JSON.stringify(result))));
      await refresh();
    }, event.submitter);
  };
}

// ---------- Dialogs ----------
function payloadView(payload) {
  const block = (label, value) => `<article class="message"><div class="message-head"><span class="tag">${escape(label)}</span></div><pre>${escape(typeof value === 'string' ? value : JSON.stringify(value, null, 2))}</pre></article>`;
  if (payload?.messages) return payload.messages.map(message => block(message.role, message.content)).join('');
  if (payload?.events) return block('Observed events', payload.events);
  const entries = Object.entries(payload || {});
  return entries.length ? entries.map(([key, value]) => block(key, value)).join('') : '<p class="muted">Empty payload.</p>';
}

async function openExample(revisionId, existing) {
  revisionId = revisionId || state.items[0]?.current_revision;
  if (!revisionId) throw new Error('Collect or import evidence first.');
  const revision = await api('revisions/' + revisionId), meta = JSON.parse(revision.metadata);
  const choices = state.items.map(item => ({id: item.current_revision, name: item.title}));
  if (!choices.some(choice => choice.id === revisionId)) choices.unshift({id: revisionId, name: revision.title});
  workDialog(existing ? 'Revise a grounded example' : 'Draft a grounded example', `<form id="example-form">
    <p>Every example cites an exact quote from one evidence revision. Saving creates a draft; approval happens separately.</p>
    <label>Evidence revision<select id="example-source">${options(choices)}</select></label>
    <details><summary>Read source evidence</summary><pre>${escape(revision.text)}</pre></details>
    <label>Format<select id="example-kind">${Object.entries(kinds).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select></label>
    <div id="example-fields"></div>
    <label>Exact supporting quote<textarea name="quote" required>${escape(existing ? revision.text.slice(existing.citations[0].start, existing.citations[0].end) : revision.text.slice(0, 300))}</textarea></label>
    <label>Review notes / preference rationale<textarea name="notes">${escape(existing?.notes || '')}</textarea></label>
    ${revision.kind === 'human_message' ? '<label>Actual target participant<input name="participant" required></label><label><input type="checkbox" name="context" required> I confirmed the context and approve this role mapping.</label>' : ''}
    <label><input type="checkbox" name="redact"> Redact detected credentials, email addresses, and phone numbers in this draft</label>
    <div class="actions"><button class="primary">${icon('check')}Save draft</button></div>
  </form>`);
  $('example-source').value = revisionId;
  $('example-source').onchange = event => action(() => openExample(event.target.value));
  $('example-kind').value = existing?.kind || 'sft';
  function fields() {
    const kind = $('example-kind').value, payload = existing?.kind === kind ? existing.payload : {};
    const entries = kind === 'sft'
      ? (payload.messages || [{role: 'user', content: ''}, {role: 'assistant', content: ''}]).map((message, index) => ({key: 'message-' + index, label: message.role, value: message.content, role: message.role}))
      : kind === 'trace' ? []
        : (kind === 'preference' ? ['prompt', 'chosen', 'rejected'] : kind === 'evaluation' ? ['prompt', 'reference'] : ['prompt', 'completion']).map(key => ({key, label: key, value: payload[key] || ''}));
    $('example-fields').innerHTML = kind === 'trace'
      ? `<p>Only recorded tool events can be used.</p><pre>${escape(JSON.stringify(meta.observed_events || [], null, 2))}</pre>`
      : entries.map(entry => `<label>${escape(entry.label.charAt(0).toUpperCase() + entry.label.slice(1))}<textarea name="${entry.key}" data-role="${entry.role || ''}" required>${escape(entry.value)}</textarea></label>`).join('');
  }
  fields();
  $('example-kind').onchange = fields;
  $('example-form').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target), kind = $('example-kind').value;
    let payload = {};
    if (kind === 'sft') payload.messages = [...$('example-fields').querySelectorAll('textarea')].map(textarea => ({role: textarea.dataset.role, content: textarea.value}));
    else if (kind === 'trace') payload.events = meta.observed_events;
    else for (const textarea of $('example-fields').querySelectorAll('textarea')) payload[textarea.name] = textarea.value;
    action(async () => {
      await api('candidate', {revision_id: revisionId, kind, payload, quote: form.get('quote'), notes: form.get('notes'), redact: form.has('redact'), parent_id: existing?.id,
        mapping: revision.kind === 'human_message' ? {target_participant: form.get('participant'), context_confirmed: form.has('context'), roles_approved: form.has('context')} : null});
      $('work-dialog').close();
      navigate('training');
      await refresh();
      notice('Draft saved. Inspect it before approval.');
    }, event.submitter);
  };
}

async function inspectCandidate(id) {
  const candidate = await api('candidates/' + id), revision = await api('revisions/' + candidate.revision_id);
  const findings = candidate.findings.map(f => f.code + ' (' + f.severity + ')').join(', ');
  workDialog('Review training example', `
    <div class="drawer-meta"><span class="tag">${icon(EXAMPLE_ICONS[candidate.kind] || 'file')}${escape(kinds[candidate.kind] || candidate.kind)}</span>${statusPill(candidate.status)}<span>${escape(originLabel(candidate.origin))}</span><span>${escape(relativeTime(candidate.created_at))}</span>${seal(candidate.hash, 'Example SHA-256')}</div>
    <div class="section-label">Example</div>
    <div class="payload">${payloadView(candidate.payload)}</div>
    <details><summary>Raw payload</summary><pre>${escape(JSON.stringify(candidate.payload, null, 2))}</pre></details>
    <div class="section-label">Supporting evidence · ${escape(revision.title)}</div>
    ${candidate.citations.map(citation => `<blockquote>${escape(citation.quote)}</blockquote>`).join('')}
    <details><summary>Full source revision</summary><pre>${escape(revision.text)}</pre></details>
    ${candidate.notes ? `<p>${escape(candidate.notes)}</p>` : ''}
    <p class="screening${findings ? '' : ' clear'}">${icon(findings ? 'alert' : 'check')}<span>${escape(findings ? 'Screening findings: ' + findings : 'No heuristic screening findings. Still review the actual content.')}</span></p>
    <label><input id="example-permission" type="checkbox"${revision.review.allowed ? ' checked' : ''}> I have permission to use this source revision.</label>
    <label><input id="example-correct" type="checkbox"> I reviewed the example, context, and answer correctness.</label>
    <label><input id="example-ack" type="checkbox"> I reviewed and accept any screening warnings.</label>
    <div class="actions"><button type="button" id="approve-example" class="primary">${icon('check')}Approve</button><button type="button" id="edit-example" class="secondary">Revise draft</button><button type="button" id="reject-example">Reject</button><button type="button" id="revoke-example" class="danger-text">Revoke</button></div>`);
  $('approve-example').onclick = () => action(async () => {
    if (!$('example-permission').checked || !$('example-correct').checked) throw new Error('Confirm source permission and example correctness.');
    await api('review', {revision_id: candidate.revision_id, allowed: true, approved: !!revision.review.approved});
    await api('candidate-review', {candidate_id: id, decision: 'approved', acknowledge: $('example-ack').checked});
    $('work-dialog').close();
    notice('Example approved.');
    await refresh();
  }, $('approve-example'));
  $('edit-example').onclick = () => action(() => openExample(candidate.revision_id, candidate));
  for (const decision of ['rejected', 'revoked']) {
    const button = $(decision === 'rejected' ? 'reject-example' : 'revoke-example');
    button.onclick = () => action(async () => {
      await api('candidate-review', {candidate_id: id, decision});
      $('work-dialog').close();
      notice(decision === 'rejected' ? 'Example rejected.' : 'Example revoked. Bundles that include it are blocked.');
      await refresh();
    }, button);
  }
}

function openCrawl() {
  const webSources = state.sources.filter(source => source.kind === 'web');
  if (!webSources.length) {
    workDialog('Collect a bounded set of pages', `<p>Add a web source first. A crawl starts from a source’s URL and stays inside its directory.</p><div class="actions"><button type="button" class="primary" data-close="work-dialog" data-open="source-dialog">${icon('plus')}Add source</button></div>`);
    return;
  }
  workDialog('Collect a bounded set of pages', `<form id="crawl-form">
    <p>Collection stays on the same origin and inside the starting URL’s directory. Robots rules, cooldowns, and daily request budgets apply.</p>
    <label>Source<select name="source_id">${options(webSources)}</select></label>
    <div class="grid-2"><label>Maximum pages<input name="max_pages" type="number" min="1" max="20" value="5"></label><label>Link depth<input name="max_depth" type="number" min="0" max="3" value="1"></label></div>
    <label><input name="render" type="checkbox"> Render inline JavaScript offline (optional Chromium; external resources blocked)</label>
    <div class="actions"><button class="primary">${icon('layers')}Start collection</button></div>
  </form>`);
  $('crawl-form').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target);
    action(async () => {
      await api('crawl', {source_id: form.get('source_id'), max_pages: Number(form.get('max_pages')), max_depth: Number(form.get('max_depth')), render: form.has('render')});
      $('work-dialog').close();
      navigate('agents');
      await refresh();
      notice('Collection queued. Pages are fetched one at a time within cooldowns.');
    }, event.submitter);
  };
}

function openRecipe() {
  workDialog('Define extracted fields', `<form id="recipe-form">
    <p>Recipes describe fields to pull from evidence. Every extracted value must quote the source; results stay unreviewed.</p>
    <label>Recipe name<input name="name" required placeholder="Article facts"></label>
    <label>One field per line, as name: description<textarea name="fields" required placeholder="title: Article title&#10;author: Named author"></textarea></label>
    <div class="actions"><button class="primary">Save recipe</button></div>
  </form>`);
  $('recipe-form').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target), fields = {};
    for (const line of form.get('fields').split('\n').filter(line => line.trim())) {
      const index = line.indexOf(':');
      if (index < 1) return notice('Use field: description on each line.', true);
      fields[line.slice(0, index).trim()] = line.slice(index + 1).trim();
    }
    action(async () => {
      await api('recipe', {name: form.get('name'), fields});
      $('work-dialog').close();
      notice('Extraction recipe saved.');
      await refresh();
    }, event.submitter);
  };
}

async function openModel(revisionId, purpose = 'sft') {
  const workbench = await api('workbench');
  if (!workbench.model.configured) throw new Error(workbench.model.detail);
  workDialog('Use your configured model', `<form id="model-form">
    <p class="callout">${icon('info')}<span>Sends up to 20,000 characters of the selected evidence to <b>${escape(workbench.model.model)}</b> at ${escape(workbench.model.url)}. Review any personal information before sending. Results remain unreviewed.</span></p>
    <label>Evidence<select name="revision_id">${options(state.items, 'current_revision', 'title')}</select></label>
    ${purpose === 'extraction' ? `<label>Recipe<select name="recipe_id">${options(workbench.recipes)}</select></label>` : ''}
    <div class="actions"><button class="primary">${icon('sparkle')}Send evidence and create draft</button></div>
  </form>`);
  if (revisionId) $('model-form').elements.revision_id.value = revisionId;
  $('model-form').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target);
    action(async () => {
      await api('model-assist', {purpose, revision_id: form.get('revision_id'), recipe_id: form.get('recipe_id')});
      $('work-dialog').close();
      navigate('training');
      await refresh();
      notice('Model result saved for review.');
    }, event.submitter);
  };
}

document.addEventListener('click', event => {
  const b = event.target.closest('button');
  if (!b) return;
  if (b.dataset.trainingFilter) { trainingFilter = b.dataset.trainingFilter; renderTraining(); }
  if (b.dataset.draftRevision) action(() => openExample(b.dataset.draftRevision));
  if (b.dataset.modelRevision) action(() => openModel(b.dataset.modelRevision));
  if (b.dataset.candidate) action(() => inspectCandidate(b.dataset.candidate));
  if (b.dataset.branchTarget) action(async () => { const candidate = await api('branch-example', {revision_id: b.dataset.branchRevision, target_id: b.dataset.branchTarget}); await inspectCandidate(candidate.id); }, b);
  if (b.dataset.cancelJob) action(async () => { await api('crawl-cancel', {job_id: b.dataset.cancelJob}); await refresh(); }, b);
  if (b.dataset.job) action(async () => {
    const job = await api('crawls/' + b.dataset.job);
    workDialog('Collection outcomes', `<div class="drawer-meta">${statusPill(job.state)}<span>${escape(job.detail || '')}</span></div>
      ${job.pages.length ? `<div class="rows">${job.pages.map(page => `<div class="row"><div><h3 class="mono">${escape(page.url)}</h3><p>Depth ${page.depth}${page.detail ? ' · ' + escape(page.detail) : ''}</p></div>${statusPill(page.state)}</div>`).join('')}</div>` : '<p class="muted">No pages recorded yet.</p>'}
      <details><summary>Raw job record</summary><pre>${escape(JSON.stringify(job, null, 2))}</pre></details>`);
  }, b);
  if (b.dataset.bundle) action(() => download('bundle/' + b.dataset.bundle, 'proofpage-' + b.dataset.bundle + '.zip'), b);
});
