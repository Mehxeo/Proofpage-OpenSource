// Workspace views: library, sources, activity, datasets, and the evidence drawer.
let state, view = 'library', query = '', pendingFile = null, pollTimer;
const filters = {kind: '', source: '', review: '', rights: ''};
let layout = (() => { try { return localStorage.getItem('proofpage-layout') === 'list' ? 'list' : 'grid'; } catch { return 'grid'; } })();

const VIEWS = {
  business: ['Business context', 'Give your assistant the right background.', 'Choose sources, review passages, and take your context to another assistant.'],
  verify: ['Check quotes', 'Does the source say that?', 'Check quoted passages against captured evidence. Review the source before trusting the answer.'],
  library: ['Library', 'A library you can trace.', 'Collect useful material. Keep the evidence behind it.'],
  sources: ['Sources', 'Every source, accounted for.', 'Set up collection and see exactly what each site allowed and returned.'],
  activity: ['Activity', 'The collection record.', 'Completed captures, access conditions, and unfinished work, newest first.'],
  datasets: ['Datasets', 'From evidence to a corpus.', 'Review individual revisions, confirm permission, then freeze an export.'],
  timeline: ['Timeline', 'What changed, and when.', 'Content edits, publisher rights changes, broken links, and collection problems across your sources.'],
  settings: ['Settings', 'Your workspace, connected.', 'Browser capture, AI assistants and evidence you control.'],
};
let evidenceContext = {};

const KIND_ICONS = {document: 'file', conversation: 'message', human_message: 'message', message: 'message', agent_trace: 'plug'};
const kindIcon = kind => KIND_ICONS[kind] || 'file';
const kindLabel = kind => String(kind || 'record').replaceAll('_', ' ');
const locationLabel = url => { try { const parsed = new URL(url); return parsed.hostname.replace(/^www\./, '') + (parsed.pathname === '/' ? '' : parsed.pathname); } catch { return url; } };
const itemRights = item => item.source_kind && item.source_kind !== 'web' ? 'user_supplied' : (item.rights?.train || 'not_recorded');
const snippetHtml = text => escape(text).replaceAll('\u0002', '<mark>').replaceAll('\u0003', '</mark>');

async function refresh() {
  state = await api('state?q=' + encodeURIComponent(query));
  render();
  schedulePoll();
}

function schedulePoll() {
  clearTimeout(pollTimer);
  const busy = state.runs.some(run => run.state === 'running');
  if (busy && ['activity', 'sources'].includes(view)) {
    pollTimer = setTimeout(() => { if (!document.querySelector('dialog[open]')) refresh().catch(() => {}); else schedulePoll(); }, 3000);
  }
}

function setHeading(label, title, subtitle) {
  $('title').textContent = title;
  $('subtitle').textContent = subtitle;
  $('breadcrumb').textContent = 'Workspace / ' + label;
  document.title = label + ' · Proofpage';
}

function markNav() {
  document.querySelectorAll('[data-view]').forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
}

let renderedView;
function render() {
  $('count').textContent = state.total ?? state.items.length;
  updateUnreadBadge(state.unread || 0);
  markNav();
  if (renderedView !== view) {
    renderedView = view;
    window.scrollTo(0, 0);
  }
  if (view === 'business') { setHeading(...VIEWS.business); action(renderBusiness); return; }
  if (view === 'verify') { setHeading(...VIEWS.verify); action(renderClaims); return; }
  if (view === 'training' || view === 'agents') {
    action(() => renderWorkbench(view));
    return;
  }
  if (view === 'timeline' || view === 'settings') {
    setHeading(...VIEWS[view]);
    action(view === 'timeline' ? renderTimeline : renderSettings);
    return;
  }
  const [label, title, subtitle] = VIEWS[view] || VIEWS.library;
  setHeading(label, title, subtitle);
  ({library: renderLibrary, sources: renderSources, activity: renderActivity, datasets: renderDatasets}[view] || renderLibrary)();
}

// ---------- Library ----------
function itemCard(item) {
  const excerpt = item.snippet ? snippetHtml(item.snippet) : escape((item.text || '').slice(0, 260));
  return `<article class="card">
    <div class="card-top"><span class="tag">${icon(kindIcon(item.kind))}${escape(kindLabel(item.kind))}</span><span class="chips">${item.approved ? '<span class="pill tone-ok">Approved</span>' : item.allowed ? '<span class="pill tone-accent">Permission given</span>' : ''}${item.source_kind === 'web' ? rightsChip(itemRights(item), 'train', true, item.rights?.summary) : ''}</span></div>
    <h3><button type="button" class="card-link" data-item="${escape(item.id)}">${escape(item.title || 'Untitled record')}</button></h3>
    <p>${excerpt || '<span class="muted">No text captured.</span>'}</p>
    <div class="card-meta"><span>${icon('globe')}${escape(item.source_name)}</span><span title="${escape(date(item.captured_at))}">${icon('clock')}${escape(relativeTime(item.captured_at))}</span>${seal(item.hash, 'Revision SHA-256')}</div>
  </article>`;
}

function onboarding() {
  return `<section class="panel onboarding">
    <div>
      
      <h2>Start a library you can trace.</h2>
      <p>Save a page, check a quote, or bring your own files. Every record keeps its source and revision history.</p>
      <div class="actions">
        <button type="button" class="primary" id="try-example">${icon('collect')}Try with example.com</button>
        <button type="button" class="secondary" data-open="source-dialog">${icon('plus')}Add your own page</button>
        <button type="button" data-open-import>${icon('upload')}Import files</button><button type="button" class="secondary" data-go="verify">${icon('check')}Check a quoted answer</button>
      </div>
    </div>
    <ol class="steps">
      <li><b>Add a public page</b><span>Paste a URL. Robots rules, cooldowns, and daily budgets are respected.</span></li>
      <li><b>Collect it</b><span>Proofpage stores the readable text, the original response, and the publisher’s AI-usage signals.</span></li>
      <li><b>Inspect the evidence</b><span>Read it, confirm permission, and turn it into reviewed training data.</span></li>
    </ol>
  </section>`;
}

function renderLibrary() {
  const items = state.items;
  if (!items.length && !state.sources.length && !query) {
    $('content').innerHTML = onboarding();
    return;
  }
  const attention = state.sources.filter(source => !['ready', 'available'].includes(source.state)).length;
  const kinds = Object.entries(items.reduce((counts, item) => ({...counts, [item.kind]: (counts[item.kind] || 0) + 1}), {}));
  if (filters.kind && !kinds.some(([kind]) => kind === filters.kind)) filters.kind = '';
  const sources = state.sources.filter(source => items.some(item => item.source_id === source.id));
  const shown = items.filter(item => (!filters.kind || item.kind === filters.kind)
    && (!filters.source || item.source_id === filters.source)
    && (!filters.review || (filters.review === 'approved' ? item.approved : !item.approved))
    && (!filters.rights || itemRights(item) === filters.rights));
  const rightsPresent = [...new Set(items.filter(item => item.source_kind === 'web').map(itemRights))];
  if (filters.rights && !rightsPresent.includes(filters.rights)) filters.rights = '';
  const chip = (group, value, label, count) => `<button type="button" class="chip" data-filter="${group}" data-value="${escape(value)}" aria-pressed="${filters[group] === value}">${escape(label)}${count === undefined ? '' : ` <span class="count">${count}</span>`}</button>`;

  $('content').innerHTML = `
    <div class="metrics">
      <div class="metric"><b>${state.total ?? items.length}</b><span>Records in your library</span></div>
      <div class="metric"><b>${state.sources.length}</b><span>Configured sources</span></div>
      <div class="metric"><b>${state.approved ?? items.filter(item => item.approved).length}</b><span>Approved for datasets</span></div>
      <div class="metric"><b>${attention}</b><span>Sources needing attention</span></div>
    </div>
    <div class="toolbar">
      <div class="searchbox">${icon('search')}<input id="search" type="search" aria-label="Search evidence" placeholder="Search your evidence and press Enter…" value="${escape(query)}"></div>
      <div class="segmented" role="group" aria-label="Layout">
        <button type="button" data-layout="grid" aria-pressed="${layout === 'grid'}" aria-label="Grid layout" title="Grid">${icon('grid')}</button>
        <button type="button" data-layout="list" aria-pressed="${layout === 'list'}" aria-label="List layout" title="List">${icon('list')}</button>
      </div>
    </div>
    <div class="toolbar">
      <div class="filters" role="group" aria-label="Filter by kind">${chip('kind', '', 'All kinds')}${kinds.map(([kind, count]) => chip('kind', kind, kindLabel(kind), count)).join('')}</div>
      <div class="filters" role="group" aria-label="Filter by review">${chip('review', '', 'Any review')}${chip('review', 'approved', 'Approved')}${chip('review', 'pending', 'Not approved')}</div>
      ${rightsPresent.length ? `<div class="filters" role="group" aria-label="Filter by AI-training rights">${chip('rights', '', 'Any rights')}${['allowed', 'conditional', 'unknown', 'reserved', 'not_recorded'].filter(v => rightsPresent.includes(v)).map(v => chip('rights', v, 'Training ' + RIGHTS[v][0].toLowerCase())).join('')}</div>` : ''}
      ${sources.length > 1 ? `<select id="source-filter" aria-label="Filter by source" class="small"><option value="">All sources</option>${sources.map(source => `<option value="${escape(source.id)}"${filters.source === source.id ? ' selected' : ''}>${escape(source.name)}</option>`).join('')}</select>` : ''}
    </div>
    <div class="section-label">${query ? `Results for “${escape(query)}” · ${shown.length}` : `Recent evidence · ${shown.length}`}</div>
    ${shown.length ? `<div class="cards${layout === 'list' ? ' list-mode' : ''}">${shown.map(itemCard).join('')}</div>`
      : query || filters.kind || filters.review || filters.source || filters.rights
        ? empty('No matching evidence.', 'Try a different word, clear a filter, or add another source.', `<button type="button" class="secondary" id="clear-search">${icon('x')}Clear search and filters</button>`, 'search')
        : empty('Collect your first source.', 'Your sources are set up. Collect one to capture its text and original evidence.', `<button type="button" class="primary" data-go="sources">${icon('globe')}Go to sources</button>`, 'collect')}`;

  $('search').addEventListener('keydown', event => {
    if (event.key === 'Enter') { query = event.target.value.trim(); action(refresh); }
    if (event.key === 'Escape' && event.target.value) { event.target.value = ''; query = ''; action(refresh); }
  });
  $('search').addEventListener('search', event => { if (!event.target.value && query) { query = ''; action(refresh); } });
  if ($('source-filter')) $('source-filter').onchange = event => { filters.source = event.target.value; renderLibrary(); };
}

// ---------- Sources ----------
function sourceCard(source) {
  const run = state.runs.find(r => r.source_id === source.id);
  const web = source.kind === 'web';
  const schedule = web ? (source.interval_seconds ? `Watching every ${source.interval_seconds >= 3600 ? (source.interval_seconds === 3600 ? 'hour' : pluralize(source.interval_seconds / 3600, 'hour')) : pluralize(source.interval_seconds / 60, 'minute')} · changes go to Timeline` : 'Not watched · manual refresh') : 'Supplied archive · source fields preserved';
  const letter = (hostname(source.location) || source.name || '?').replace(/[^a-z0-9]/gi, '')[0] || '?';
  const live = web && /^https?:\/\//i.test(source.location);
  return `<article class="card source-card">
    <div class="card-top"><span class="monogram" aria-hidden="true">${escape(letter)}</span><div><h3>${escape(source.name)}</h3><span class="location" title="${escape(source.location)}">${escape(web ? locationLabel(source.location) : source.location)}</span></div>${statusPill(source.state)}</div>
    <p class="help">${escape(run?.detail || stateInfo(source.state).help || 'Configured.')}</p>
    ${web ? (() => { const verdict = source.rights ? JSON.parse(source.rights) : null; return `<div class="chips">${verdict ? Object.keys(RIGHTS_USES).map(use => rightsChip(verdict[use], use, true, verdict.summary)).join('') : rightsChip('not_recorded')}</div>`; })() : ''}
    <div class="card-meta"><span>${icon(web ? 'clock' : 'folder')}${escape(schedule)}${run ? ' · last run ' + escape(relativeTime(run.finished_at || run.started_at)) : ''}</span>
      ${web ? `<div class="actions">
        ${live ? `<a class="button icon-button small" href="${escape(source.location)}" target="_blank" rel="noopener noreferrer" aria-label="Open live page" title="Open live page">${icon('external')}</a>` : ''}
        <button type="button" class="icon-button small" data-wacz="${escape(source.id)}" data-wacz-name="${escape(hostname(source.location))}" aria-label="Export as a WACZ web archive" title="Export as a WACZ web archive with signed receipts">${icon('download')}</button>
        <button type="button" class="small" data-schedule="${escape(source.id)}" data-interval="${source.interval_seconds ? 0 : 3600}" title="Choose how often to collect this source while Proofpage runs">${icon(source.interval_seconds ? 'pause' : 'eye')}${source.interval_seconds ? 'Edit schedule' : 'Set schedule'}</button>
        <button type="button" class="secondary small" data-collect="${escape(source.id)}">${icon('collect')}Collect</button>
      </div>` : ''}
    </div>
  </article>`;
}

function renderSources() {
  const profileName = id => state.profiles.find(profile => profile.id === id)?.name || 'Unknown profile';
  $('content').innerHTML = `
    <div class="toolbar"><div class="actions">
      <button type="button" class="secondary" id="crawl-open">${icon('layers')}Collect multiple pages</button>
      <button type="button" data-new-profile>${icon('user')}Create import profile</button>
      <button type="button" id="watch-open">${icon('folder')}Watch an export folder</button>
    </div></div>
    ${state.sources.length ? `<div class="cards">${state.sources.map(sourceCard).join('')}</div>`
      : empty('Connect your first source.', 'Add a public page or choose an archive to begin.', `<button type="button" class="primary" data-open="source-dialog">${icon('plus')}Add source</button><button type="button" class="secondary" data-open-import>${icon('upload')}Import files</button>`, 'globe')}
    <div class="section-label">Import profiles · ${state.profiles.length}</div>
    ${state.profiles.length ? `<div class="rows">${state.profiles.map(profile => `<div class="row"><div><h3>${escape(profile.name)}</h3><p>${escape(profile.provider)} · ${escape(profile.account)} · ${escape(profile.adapter)}</p></div><span class="pill">Local import profile</span></div>`).join('')}</div>`
      : '<p class="muted">Profiles keep each exported account separate. Create one before importing an archive.</p>'}
    <div class="section-label">Watched folders · ${state.watches.length}</div>
    ${state.watches.length ? `<div class="rows">${state.watches.map(watch => `<div class="row"><div><h3>${escape(profileName(watch.profile_id))}</h3><p class="mono">${escape(watch.directory)}</p><p>${escape(JSON.parse(watch.categories).join(', '))}${watch.detail ? ' · ' + escape(watch.detail) : ''}</p></div><div class="actions">${statusPill(watch.state)}<button type="button" class="small" data-watch-toggle="${escape(watch.id)}" data-enabled="${watch.enabled ? 'false' : 'true'}">${watch.enabled ? 'Pause' : 'Resume'}</button><button type="button" class="small" data-watch-scan="${escape(watch.id)}">Check now</button><button type="button" class="small" data-watch-detail="${escape(watch.id)}">File outcomes</button></div></div>`).join('')}</div>`
      : '<p class="muted">Watch a folder to import new exports automatically while Proofpage is open.</p>'}`;
  $('watch-open').onclick = () => { profileOptions(); $('watch-dialog').showModal(); };
  $('crawl-open').onclick = () => openCrawl();
}

// ---------- Activity ----------
function renderActivity() {
  if (!state.runs.length) {
    $('content').innerHTML = empty('No collection runs yet.', 'When you collect a source, each outcome appears here — including pages that were blocked, rate limited, or unchanged.', `<button type="button" class="primary" data-go="sources">${icon('globe')}Go to sources</button>`, 'activity');
    return;
  }
  const days = new Map();
  for (const run of state.runs) {
    const day = new Date(run.started_at).toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'});
    days.set(day, [...(days.get(day) || []), run]);
  }
  $('content').innerHTML = `<div class="timeline">${[...days].map(([day, runs]) => `<section class="day"><h4>${escape(day)}</h4><ol>${runs.map(run => {
    const source = state.sources.find(s => s.id === run.source_id);
    const tone = stateInfo(run.state).tone.split(' ')[0];
    return `<li class="event"${tone ? ` data-tone="${tone}"` : ''}><div><h3>${escape(source?.name || run.source_id)}</h3><p>${escape(run.detail || 'Collection in progress')}</p><p class="muted">${pluralize(run.added, 'new revision')}</p></div><div class="actions">${statusPill(run.state)}<time datetime="${escape(run.started_at)}" title="${escape(date(run.started_at))}">${escape(new Date(run.started_at).toLocaleTimeString(undefined, {hour: 'numeric', minute: '2-digit'}))}</time></div></li>`;
  }).join('')}</ol></section>`).join('')}</div>`;
}

// ---------- Datasets ----------
function renderDatasets() {
  $('content').innerHTML = `
    <div class="panel panel-head"><div><h3>Freeze a reviewed corpus</h3><p>Exports clean corpus JSONL from revisions you approved and have permission to use. Human messages keep their kind. This does not train a model or create assistant targets.</p></div><button type="button" class="primary" id="freeze">${icon('layers')}Freeze reviewed corpus</button></div>
    <div class="section-label">Frozen datasets · ${state.datasets.length}</div>
    ${state.datasets.length ? `<div class="cards">${state.datasets.map(dataset => `<article class="card dataset-card">
      <div class="card-top"><span class="tag">${icon(dataset.format ? 'training' : 'database')}${dataset.format ? escape(kinds[dataset.format] || dataset.format) : 'Corpus JSONL'}</span>${seal(dataset.hash, 'Dataset SHA-256')}</div>
      ${datasetRightsFlag(dataset)}
      <h3>${escape(dataset.name)}</h3>
      <p>Frozen ${escape(relativeTime(dataset.created_at))}. ${dataset.format ? 'Training examples as JSONL; download the full bundle from Training.' : 'Every export re-checks permission, publisher rights, and integrity.'}</p>
      <div class="card-meta"><span title="${escape(date(dataset.created_at))}">${icon('clock')}${escape(date(dataset.created_at))}</span><span class="actions"><button type="button" class="small" data-docs="${escape(dataset.id)}" data-docs-name="${escape(dataset.name)}">${icon('file')}Documentation</button><button type="button" class="secondary small" data-export="${escape(dataset.id)}">${icon('download')}Export JSONL</button></span></div>
    </article>`).join('')}</div>`
      : empty('Review before you export.', 'Open a library record, review its evidence, and confirm permission. Frozen exports use exactly the approved revisions.', `<button type="button" class="secondary" data-go="library">${icon('library')}Open the library</button>`, 'database')}`;
  $('freeze').onclick = () => action(async () => {
    const result = await api('freeze', {name: 'Reviewed corpus · ' + new Date().toLocaleDateString()});
    notice(`Frozen ${pluralize(result.records, 'reviewed record')}.` + rightsCounts(result.rights));
    await refresh();
  }, $('freeze'));
}

// ---------- Evidence drawer ----------
function conversationView(metadata) {
  const normalized = metadata.normalized;
  if (!normalized?.messages) return '';
  const labels = new Map(normalized.messages.map((message, index) => [message.id, 'Message ' + (index + 1)]));
  return `<details open><summary>Source conversation · ${pluralize(normalized.messages.length, 'message')}</summary><p class="muted">${escape(normalized.branching)}</p>${normalized.messages.map((message, index) => `<article class="message"><div class="message-head"><span class="tag">${escape(message.role || 'Unknown source role')}</span><strong>Message ${index + 1}</strong></div><p class="muted">${message.parent ? 'Replies to ' + escape(labels.get(message.parent) || 'a missing source message') : 'Parent relationship not supplied'}${message.children?.length > 1 ? ' · ' + message.children.length + ' source branches' : ''}</p><pre>${escape(message.text || 'No text supplied for this node.')}</pre></article>`).join('')}</details>`;
}

function signalRow(signal) {
  return `<div class="signal"><div class="signal-head"><b>${escape(signal.label)}</b>${Object.entries(signal.effects).map(([use, value]) => rightsChip(value, use)).join('')}</div>
    <code>${escape(signal.raw)}</code><small>${escape(signal.source)} · ${escape(signal.status)}${signal.note ? ' · ' + escape(signal.note) : ''}</small></div>`;
}

function rightsPanel(rights, review) {
  if (rights.state !== 'observed') {
    return `<p class="callout">${icon('info')}<span>${escape(rights.summary)}</span></p>`;
  }
  const current = rights.current, capture = rights.at_capture;
  return `<div class="rights-grid">${Object.keys(RIGHTS_USES).map(use => `<div class="rights-use"><span class="muted">${RIGHTS_USES[use]}</span>${rightsChip(rights[use], use, false)}</div>`).join('')}</div>
    <p>${escape(rights.summary)}</p>
    ${rights.drifted ? `<p class="screening">${icon('alert')}<span>Signals changed after this revision was captured. At capture, AI training was ${escape((RIGHTS[capture.verdict.train] || RIGHTS.unknown)[0].toLowerCase())}; now it is ${escape((RIGHTS[current.verdict.train] || RIGHTS.unknown)[0].toLowerCase())}. Proofpage uses the stricter of the two.</span></p>` : ''}
    ${review.rights_basis ? `<p class="screening clear">${icon('shield')}<span>Recorded rights basis: ${escape(RIGHTS_BASES[review.rights_basis] || review.rights_basis)}${review.rights_note ? ' — ' + escape(review.rights_note) : ''}</span></p>` : ''}
    <div class="section-label">Publisher signals · ${current.signals.length}</div>
    ${current.signals.length ? current.signals.map(signalRow).join('') : '<p class="muted">No machine-readable AI-usage signals were published for this page.</p>'}
    <div class="section-label">What Proofpage checked</div>
    <dl class="meta-grid">${Object.entries(current.checked).map(([where, outcome]) => `<dt>${escape(where)}</dt><dd>${escape(outcome)}</dd>`).join('')}</dl>
    <p class="muted">Observed ${escape(relativeTime(current.observed_at))} for ${escape(rights.url)}. Signals are advisory; several are drafts or vendor conventions. This is not legal advice.</p>`;
}

function basisFields(rights, review) {
  if (rights?.train !== 'reserved') return '';
  return `<div class="basis"><label>Rights basis — required because the publisher reserved AI training<select id="rights-basis"><option value="">Choose a basis…</option>${Object.entries(RIGHTS_BASES).map(([key, label]) => `<option value="${key}"${review.rights_basis === key ? ' selected' : ''}>${label}</option>`).join('')}</select></label>
    <label>Basis note<input id="rights-note" maxlength="1000" placeholder="License reference, agreement date, or other evidence" value="${escape(review.rights_note || '')}"></label></div>`;
}

function basisPayload() {
  return $('rights-basis') ? {rights_basis: $('rights-basis').value, rights_note: $('rights-note').value} : {};
}

function evidenceTabs(tabs) {
  $('evidence-tabs').innerHTML = tabs.map(([id, label], index) => `<button type="button" role="tab" id="tab-${id}" aria-controls="panel-${id}" aria-selected="${index === 0}" tabindex="${index === 0 ? 0 : -1}">${label}</button>`).join('');
}

async function showEvidence(id, revision, options = {}) {
  const item = await api(revision ? 'revisions/' + revision : 'items/' + id);
  evidenceContext = {id, revision, options};
  const metadata = JSON.parse(item.metadata || '{}');
  const findings = item.findings || [];
  const branchTargets = (metadata.normalized?.messages || []).filter(message => message.role === 'assistant' && message.id);
  $('evidence-title').textContent = item.title || 'Untitled record';
  $('evidence-kicker').innerHTML = `<span class="tag">${icon(kindIcon(item.kind))}${escape(kindLabel(item.kind))}</span>${item.rights?.state === 'observed' || item.rights?.state === 'not_recorded' ? rightsChip(item.rights.train, 'train', true, item.rights.summary) : ''}${item.is_current === false ? '<span class="pill tone-warn">Earlier revision</span>' : ''}`;
  $('evidence-meta').innerHTML = `<span>${icon('globe', 'icon-sm')}${escape(item.source_name)}</span><span title="${escape(date(item.captured_at))}">${icon('clock', 'icon-sm')}Captured ${escape(relativeTime(item.captured_at))}</span>${seal(item.hash, 'Revision SHA-256')}${item.proof && item.proof.state !== 'none' ? proofPill(item.proof.state) : ''}${/^https?:\/\//i.test(metadata.url || '') ? `<a href="${escape(metadata.url)}" target="_blank" rel="noopener noreferrer">${icon('external', 'icon-sm')}Live page</a>` : ''}`;
  evidenceTabs([['reader', 'Reader'], ['rights', 'Rights'], ['original', 'Original evidence'], ['provenance', 'Provenance'], ['proof', 'Proof'], ['versions', `Versions <span class="count">${item.revisions.length}</span>`]]);
  const provenance = [
    ['Source', escape(item.source_name)],
    ['Kind', escape(kindLabel(item.kind))],
    ['Captured', escape(date(item.captured_at))],
    ['Source timestamp', escape(item.source_time || 'Not supplied — capture time is not source freshness.')],
    ['Revision SHA-256', `<code>${escape(item.hash)}</code> ${seal(item.hash, 'Revision SHA-256')}`],
    ['Revision ID', `<code>${escape(item.current_revision)}</code>`],
    ...(metadata.url ? [['URL', escape(metadata.url)]] : []),
    ...(metadata.status ? [['HTTP status', escape(metadata.status)]] : []),
    ...(metadata.coverage ? [['Coverage', escape(metadata.coverage)]] : []),
    ...(metadata.rendered ? [['Rendering', `Offline render · ${escape(metadata.requests)} requests, ${escape(metadata.blocked_requests)} blocked`]] : []),
  ];
  $('evidence').innerHTML = `
    <section role="tabpanel" id="panel-reader" aria-labelledby="tab-reader">
      ${item.is_current === false ? `<p class="callout">${icon('info')}<span>You are viewing an earlier revision. Review and revocation apply to this version.</span></p>` : ''}
      ${findings.length ? `<p class="screening">${icon('alert')}<span>Screening: ${escape(findings.map(f => f.code + ' (' + f.severity + ')').join(', '))}. Original evidence is never changed; redact in a training draft.</span></p>` : ''}
      ${originalFileView(item, metadata)}
      ${conversationView(metadata)}
      <div class="reader">${escape(item.text) || '<span class="muted">No readable text was captured.</span>'}</div>
      ${branchTargets.length ? `<details><summary>Create an SFT draft from one supplied branch</summary><div class="actions">${branchTargets.map(message => `<button type="button" class="secondary small" data-branch-target="${escape(message.id)}" data-branch-revision="${escape(item.current_revision)}">${icon('branch')}${escape(message.text.slice(0, 80) || message.id)}</button>`).join('')}</div></details>` : ''}
    </section>
    <section role="tabpanel" id="panel-rights" aria-labelledby="tab-rights" hidden>${rightsPanel(item.rights, item.review)}</section>
    <section role="tabpanel" id="panel-original" aria-labelledby="tab-original" hidden>
      ${metadata.asset ? originalFileView(item, metadata) : `<p class="muted">Original evidence as captured or supplied.</p><pre>${escape(item.raw)}</pre>`}
    </section>
    <section role="tabpanel" id="panel-provenance" aria-labelledby="tab-provenance" hidden>
      <dl class="meta-grid">${provenance.map(([term, value]) => `<dt>${term}</dt><dd>${value}</dd>`).join('')}</dl>
      <details><summary>Full capture metadata</summary><pre>${escape(JSON.stringify(metadata, null, 2))}</pre></details>
    </section>
    <section role="tabpanel" id="panel-proof" aria-labelledby="tab-proof" hidden>${proofPanel(item.proof, item)}</section>
    <section role="tabpanel" id="panel-versions" aria-labelledby="tab-versions" hidden><div class="skeleton"></div></section>`;
  await loadOriginalPreview(item, metadata);
  $('evidence-foot').innerHTML = `${basisFields(item.rights, item.review)}
    <label><input id="permission" type="checkbox"${item.review.allowed ? ' checked' : ''}> I have permission to include this revision in a dataset.</label>
    <label><input id="approved" type="checkbox"${item.review.approved ? ' checked' : ''}> I reviewed and approve it for a clean corpus.</label>
    <div class="actions">
      <button type="button" class="small" data-model-revision="${escape(item.current_revision)}">${icon('sparkle')}Draft with my model</button>
      <button type="button" class="secondary small" data-draft-revision="${escape(item.current_revision)}">${icon('training')}Create training example</button>
      <button type="button" class="small danger-text" id="revoke">Revoke permission</button>
      <button type="button" class="primary small" id="review">${icon('check')}Save review</button>
    </div>`;
  $('review').onclick = () => action(async () => {
    await api('review', {revision_id: item.current_revision, allowed: $('permission').checked, approved: $('approved').checked, ...basisPayload()});
    $('evidence-dialog').close();
    notice('Review saved for this revision.');
    await refresh();
  }, $('review'));
  $('revoke').onclick = () => action(async () => {
    await api('review', {revision_id: item.current_revision, allowed: false, approved: false});
    $('evidence-dialog').close();
    notice('Permission revoked. Managed exports containing this revision are blocked.');
    await refresh();
  }, $('revoke'));
  $('evidence').scrollTop = 0;
  if (!$('evidence-dialog').open) $('evidence-dialog').showModal();
  if (options.tab) selectTab($('tab-' + options.tab));
}

function selectTab(tab) {
  tab.closest('[role=tablist]').querySelectorAll('[role=tab]').forEach(other => {
    const selected = other === tab;
    other.setAttribute('aria-selected', String(selected));
    other.tabIndex = selected ? 0 : -1;
    const panel = $(other.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
  tab.focus();
  if (tab.id === 'tab-versions' && !tab.dataset.loaded) {
    tab.dataset.loaded = '1';
    action(() => loadVersions(evidenceContext.options || {}));
  }
}

document.addEventListener('keydown', event => {
  const tab = event.target.closest('[role=tab]');
  if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const tabs = [...tab.closest('[role=tablist]').querySelectorAll('[role=tab]')];
  const index = tabs.indexOf(tab);
  const next = {ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: tabs.length - 1}[event.key];
  event.preventDefault();
  selectTab(tabs[(next + tabs.length) % tabs.length]);
});

// ---------- Documentation drafts ----------
let documentationDrafts;
async function openDocs(datasetId, name) {
  const docs = await api('compliance/' + datasetId);
  documentationDrafts = {docs, slug: String(name || 'dataset').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'dataset'};
  openModal('Documentation drafts', `
    <p class="callout">${icon('info')}<span>Built only from what Proofpage recorded for “${escape(name)}”. These are drafts, not legal advice; review and complete them before publishing.</span></p>
    <div class="tabs" role="tablist" aria-label="Documents">
      <button type="button" role="tab" id="tab-doc-summary" aria-controls="panel-doc-summary" aria-selected="true">EU AI Act summary</button>
      <button type="button" role="tab" id="tab-doc-card" aria-controls="panel-doc-card" aria-selected="false" tabindex="-1">Dataset card</button>
      <button type="button" role="tab" id="tab-doc-croissant" aria-controls="panel-doc-croissant" aria-selected="false" tabindex="-1">Croissant</button>
    </div>
    <section role="tabpanel" id="panel-doc-summary" aria-labelledby="tab-doc-summary"><pre>${escape(docs.summary_markdown)}</pre></section>
    <section role="tabpanel" id="panel-doc-card" aria-labelledby="tab-doc-card" hidden><pre>${escape(docs.dataset_card)}</pre></section>
    <section role="tabpanel" id="panel-doc-croissant" aria-labelledby="tab-doc-croissant" hidden><pre>${escape(JSON.stringify(docs.croissant, null, 2))}</pre></section>
    <div class="actions">
      <button type="button" class="primary small" data-save-doc="summary">${icon('download')}Summary (.md)</button>
      <button type="button" class="secondary small" data-save-doc="json">Summary (.json)</button>
      <button type="button" class="secondary small" data-save-doc="card">Dataset card (.md)</button>
      <button type="button" class="secondary small" data-save-doc="croissant">croissant.json</button>
    </div>`);
}

// ---------- Actions ----------
async function tryExample(button) {
  await action(async () => {
    const source = await api('sources', {name: 'Example Domain', url: 'https://example.com/'});
    notice('Collecting example.com… robots rules are checked first.');
    const result = await api('collect', {source_id: source.id});
    notice(result.detail + rightsNote(result.rights), result.state !== 'available');
    await refresh();
  }, button);
}

document.addEventListener('click', event => {
  const b = event.target.closest('button');
  if (!b) return;
  if (b.dataset.view) { navigate(b.dataset.view); action(refresh); }
  if (b.dataset.go) { navigate(b.dataset.go); action(refresh); }
  if (b.dataset.close) $(b.dataset.close).close();
  if (b.dataset.open) $(b.dataset.open).showModal();
  if (b.hasAttribute('data-open-import')) $('import-open').click();
  if (b.hasAttribute('data-new-profile')) $('profile-dialog').showModal();
  if (b.id === 'try-example') tryExample(b);
  if (b.id === 'clear-search') { query = ''; Object.keys(filters).forEach(key => { filters[key] = ''; }); action(refresh); }
  if (b.dataset.filter) { filters[b.dataset.filter] = b.dataset.value; renderLibrary(); }
  if (b.dataset.layout) { layout = b.dataset.layout; try { localStorage.setItem('proofpage-layout', layout); } catch {} renderLibrary(); }
  if (b.getAttribute('role') === 'tab' && b.closest('[role=tablist]')) selectTab(b);
  if (b.dataset.docs) action(() => openDocs(b.dataset.docs, b.dataset.docsName), b);
  if (b.dataset.saveDoc && documentationDrafts) {
    const {docs, slug} = documentationDrafts;
    const files = {summary: [`${slug}-training-content-summary.md`, docs.summary_markdown], json: [`${slug}-training-content-summary.json`, JSON.stringify(docs.summary, null, 2), 'application/json'],
      card: [`${slug}-dataset-card.md`, docs.dataset_card], croissant: [`${slug}-croissant.json`, JSON.stringify(docs.croissant, null, 2), 'application/ld+json']};
    saveText(...files[b.dataset.saveDoc]);
  }
  if (b.dataset.watchToggle) action(async () => { await api('watch-toggle', {watch_id: b.dataset.watchToggle, enabled: b.dataset.enabled === 'true'}); await refresh(); }, b);
  if (b.dataset.watchScan) action(async () => { const result = await api('watch-scan', {watch_id: b.dataset.watchScan}); notice(result.detail || result.state); await refresh(); }, b);
  if (b.dataset.watchDetail) action(async () => {
    const files = await api('watches/' + b.dataset.watchDetail);
    openModal('Folder processing outcomes', files.length ? `<div class="rows">${files.map(file => `<div class="row"><div><h3 class="mono">${escape(file.path)}</h3><p>${escape(file.detail)}</p></div>${statusPill(file.state)}</div>`).join('')}</div>` : '<p>No files have been observed yet.</p>');
  }, b);
  if (b.dataset.item) openItem(b.dataset.item);
  if (b.dataset.revision) action(() => showEvidence(b.dataset.record, b.dataset.revision));
  if (b.dataset.collect) action(async () => {
    notice('Collecting the requested page… robots rules are checked first.');
    const result = await api('collect', {source_id: b.dataset.collect});
    notice(result.detail + rightsNote(result.rights), result.state !== 'available');
    await refresh();
  }, b);
  if (b.dataset.schedule) {
    const source = state.sources.find(s => s.id === b.dataset.schedule);
    if (!source) return;
    const current = Number(source.interval_seconds || 0);
    const presets = [[0, 'Manual only / paused'], [900, 'Every 15 minutes'], [3600, 'Every hour'], [21600, 'Every 6 hours'], [86400, 'Every day']];
    if (current && !presets.some(([value]) => value === current)) presets.push([current, `Current: every ${current} seconds`]);
    openModal('Schedule collection', `<form id="schedule-form"><p>Keep <b>${escape(source.name)}</b> up to date. Changes appear in Timeline.</p><label>Collect this source<select name="interval_seconds">${presets.map(([value,label]) => `<option value="${value}"${value === current ? ' selected' : ''}>${escape(label)}</option>`).join('')}</select></label><p class="callout">${icon('clock')}<span>Leave Proofpage running. Collection pauses when the app closes. Site cooldowns and daily budgets may delay a run. Your first scheduled check starts after the selected interval.</span></p><div class="actions"><button type="submit" class="primary">Save schedule</button></div><p class="dialog-error" role="alert"></p></form>`);
    $('schedule-form').onsubmit = event => { event.preventDefault(); action(async () => {
      const interval = Number(new FormData(event.target).get('interval_seconds'));
      await api('schedule', {source_id: source.id, interval_seconds: interval});
      $('work-dialog').close(); await refresh(); notice(interval ? 'Schedule saved. Keep Proofpage running to collect updates.' : 'Schedule paused. You can still collect manually.');
    }, event.submitter); };
  }
  if (b.dataset.originalFile) action(() => download('original-file/' + b.dataset.originalFile, b.dataset.filename), b);
  if (b.dataset.fileBundle) action(() => download('file-bundle/' + b.dataset.fileBundle, 'proofpage-file-bundle.zip'), b);
  if (b.dataset.export) action(() => download('export/' + b.dataset.export, 'proofpage-' + b.dataset.export + '.jsonl'), b);
});

$('evidence-dialog').addEventListener('close', () => {
  if (view === 'timeline') action(refresh);
  if (!location.hash.startsWith('#/item/')) return;
  if (openedItemFromApp) { openedItemFromApp = false; history.back(); }
  else history.replaceState(null, '', '#/' + view);
});

$('source-open').onclick = () => $('source-dialog').showModal();
$('import-open').onclick = () => { profileOptions(); $('import-dialog').showModal(); };

function profileOptions(selected) {
  for (const id of ['import-profile', 'watch-profile']) {
    const select = $(id);
    const previous = selected || select.value;
    select.innerHTML = '<option value="">Choose an account profile</option>' + state.profiles.map(profile => `<option value="${escape(profile.id)}">${escape(profile.name)} · ${escape(profile.account)}</option>`).join('');
    select.value = previous;
  }
}

$('adapter').onchange = () => { $('mapping-fields').hidden = $('adapter').value !== 'mapping'; };

$('profile-form').onsubmit = event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const mapping = {};
  for (const key of ['text', 'id', 'title', 'role', 'timestamp']) if (form.get('map_' + key)) mapping[key] = form.get('map_' + key);
  action(async () => {
    const profile = await api('profiles', {name: form.get('name'), provider: form.get('provider'), account: form.get('account'), adapter: form.get('adapter'), mapping});
    $('profile-dialog').close();
    event.target.reset();
    $('mapping-fields').hidden = true;
    await refresh();
    profileOptions(profile.id);
    notice('Account-specific import profile created.');
  }, event.submitter);
};

$('watch-form').onsubmit = event => {
  event.preventDefault();
  const form = new FormData(event.target);
  action(async () => {
    await api('watches', {profile_id: form.get('profile_id'), directory: form.get('directory'), categories: form.get('categories').split(',').map(s => s.trim()).filter(Boolean)});
    $('watch-dialog').close();
    event.target.reset();
    navigate('sources');
    await refresh();
    notice('Folder watch created. Existing and future matching files will be imported after they settle.');
  }, event.submitter);
};

$('source-form').onsubmit = event => {
  event.preventDefault();
  const form = new FormData(event.target);
  action(async () => {
    const source = await api('sources', {name: form.get('name').trim() || new URL(form.get('url')).hostname, url: form.get('url')});
    if (form.get('collect_now')) { notice('Source saved. Collecting the page…'); await api('collect', {source_id: source.id}); }
    $('source-dialog').close();
    event.target.reset();
    navigate('sources');
    await refresh();
    notice(form.get('collect_now') ? 'Collection finished. Open the source to inspect its outcome.' : 'Source saved. Choose Collect when you’re ready.');
  }, event.submitter);
};

$('file').onchange = () => action(async () => {
  pendingFile = null;
  $('import-confirm').disabled = true;
  const file = $('file').files[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) throw new Error('Choose a file smaller than 8 MiB.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  pendingFile = {filename: file.name, data: btoa(binary)};
  const entries = await api('preview', pendingFile);
  $('preview').innerHTML = entries.map(entry => `<label><input type="checkbox" name="entry" value="${escape(entry.name)}"> <span><b>${escape(entry.name)}</b><br><span class="muted">${Math.ceil(entry.bytes / 1024)} KB · ${pluralize(entry.records, 'record')}${entry.error ? ' · ' + escape(entry.error) : ''}</span></span></label>`).join('') || '<p>No supported files found.</p>';
  $('import-confirm').disabled = !entries.length;
});

$('import-confirm').onclick = () => action(async () => {
  const selected = [...document.querySelectorAll('[name=entry]:checked')].map(entry => entry.value);
  const result = await api('import', {...pendingFile, selected, profile_id: $('import-profile').value});
  $('import-dialog').close();
  navigate('library');
  query = '';
  await refresh();
  notice(`Imported ${pluralize(result.added, 'new revision')} from ${pluralize(result.processed, 'record')}.` + (result.errors.length ? ' Some entries could not be imported: ' + JSON.stringify(result.errors) : ''), !!result.errors.length);
}, $('import-confirm'));

action(async () => {
  const response = await fetch('/api/session');
  if (response.status === 401) { location.href = '/login'; return; }
  const session = await response.json();
  token = session.token;
  hostingMode = session.mode || 'local';
  await applyRoute(true);
  startNotifications();
});


function originalFileView(item, metadata) {
  const asset = metadata.asset;
  if (!asset) return '';
  return `<div class="file-evidence"><h3>${escape(asset.filename)}</h3>
    <p>${escape(asset.mime)} · ${(asset.bytes / 1024).toFixed(1)} KiB · Original file retained</p>
    ${asset.mime.startsWith('image/') ? `<img class="original-image" data-original-preview alt="User-supplied image: ${escape(asset.filename)}" loading="lazy">` : '<p>Download the PDF to view it in your trusted PDF reader.</p>'}
    <button type="button" class="primary" data-original-file="${escape(item.current_revision)}" data-filename="${escape(asset.filename)}">Download original file</button>
    <button type="button" class="secondary" data-file-bundle="${escape(item.current_revision)}">File + hash manifest</button>
    <p class="muted">${escape(metadata.extraction ? 'Extraction: ' + metadata.extraction.status + '. ' + metadata.extraction.warning : 'No text extraction was performed in this older capture.')} Embedded file metadata is preserved.</p>
    <details><summary>File SHA-256</summary><code>${escape(asset.sha256)}</code></details></div>`;
}

let originalPreviewURL;
async function loadOriginalPreview(item, metadata) {
  if (originalPreviewURL) URL.revokeObjectURL(originalPreviewURL);
  originalPreviewURL = null;
  if (!metadata.asset?.mime.startsWith('image/')) return;
  const response = await fetch('/api/original-file/' + encodeURIComponent(item.current_revision) + '?preview=1', {headers:{Authorization:'Bearer ' + token}});
  if (!response.ok) throw new Error('Could not load original image.');
  const blob = await response.blob();
  // A later drawer navigation must not attach this image to a different record.
  if (!document.querySelector(`[data-original-file="${item.current_revision}"]`)) return;
  originalPreviewURL = URL.createObjectURL(blob);
  document.querySelectorAll('[data-original-preview]').forEach(image => {image.src=originalPreviewURL;});
}
$('evidence-dialog').addEventListener('close', () => {if(originalPreviewURL) URL.revokeObjectURL(originalPreviewURL); originalPreviewURL=null;});
