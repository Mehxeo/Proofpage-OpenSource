// Time Machine: the change inbox (Timeline view), revision comparison in the evidence drawer, and opt-in notifications.
let timelineFilter = '', timelineUnseen = false, versionsState, notifyTimer, lastUnread = null;
const CHANGE_KINDS = {
  content_changed: ['Content changed', 'refresh', 'info'],
  rights_drift: ['Rights changed', 'shield', 'warn'],
  link_rot: ['Link broken', 'link', 'danger'],
  collection_problem: ['Collection problem', 'alert', 'danger'],
};
const NUMBER_RE = /[$€£¥]?\d[\d,.]*%?/g;

function updateUnreadBadge(count) {
  $('unread').hidden = !count;
  $('unread').textContent = count > 99 ? '99+' : String(count || '');
  $('unread').title = pluralize(count || 0, 'unread change');
}

// ---------- Timeline view ----------
function changeStats(stats) {
  if (!stats) return '';
  const chips = [];
  if (stats.words_added) chips.push(`<span class="pill tone-ok">+${stats.words_added} words</span>`);
  if (stats.words_removed) chips.push(`<span class="pill tone-danger">−${stats.words_removed} words</span>`);
  if (stats.changed_ratio) chips.push(`<span class="pill">${Math.max(1, Math.round(stats.changed_ratio * 100))}% of words</span>`);
  for (const number of (stats.numbers_changed || []).slice(0, 4)) chips.push(`<span class="pill tone-warn num-change">${escape(number.old)} → ${escape(number.new)}</span>`);
  return chips.length ? `<div class="chips start">${chips.join('')}</div>` : '';
}

function changeCard(row) {
  const [label, iconName, tone] = CHANGE_KINDS[row.kind] || [row.kind, 'info', ''];
  const d = row.detail;
  const title = d.title || d.source_name || d.url || 'Source';
  let body = `<p>${escape(d.summary || '')}</p>`, actions = '';
  if (row.kind === 'content_changed') {
    body += changeStats(d.stats);
    actions = `<button type="button" class="secondary small" data-compare="${escape(d.item_id)}" data-from="${escape(d.from_revision)}" data-to="${escape(d.to_revision)}" data-change="${escape(row.id)}">${icon('columns')}Compare versions</button>`;
  } else if (row.kind === 'rights_drift') {
    body = `<div class="chips start">${Object.entries(d.changes || {}).map(([use, [before, after]]) => `<span class="pill${RIGHTS[after]?.[1] ? ' tone-' + RIGHTS[after][1] : ''}">${escape(RIGHTS_USES[use] || use)}: ${escape((RIGHTS[before] || RIGHTS.unknown)[0])} → ${escape((RIGHTS[after] || RIGHTS.unknown)[0])}</span>`).join('')}</div><p>${escape(d.summary || '')}</p>`
      + (d.datasets?.length ? `<p class="muted">${pluralize(d.datasets.length, 'frozen dataset')} include this page.</p>` : '');
    actions = `<button type="button" class="small" data-go="${d.datasets?.length ? 'datasets' : 'sources'}" data-change="${escape(row.id)}">${icon(d.datasets?.length ? 'database' : 'globe')}${d.datasets?.length ? 'Review datasets' : 'Open sources'}</button>`;
  } else if (row.kind === 'link_rot') {
    actions = `<button type="button" class="secondary small" data-open-change="${escape(d.item_id)}" data-change="${escape(row.id)}">${icon('eye')}Open last capture</button>`;
  } else {
    actions = `<button type="button" class="small" data-go="sources" data-change="${escape(row.id)}">${icon('globe')}Open sources</button>`;
  }
  const where = [d.source_name && d.source_name !== title ? d.source_name : '', d.url || ''].filter(Boolean).join(' · ');
  return `<li class="event change${row.seen ? '' : ' unread'}" data-tone="${tone}">
    <div class="change-body">
      <div class="change-head"><span class="tag">${icon(iconName)}${label}</span>${row.seen ? '' : '<span class="pill tone-accent">New</span>'}</div>
      <h3>${escape(title)}</h3>${body}${where ? `<p class="muted mono-ish">${escape(where)}</p>` : ''}
    </div>
    <div class="actions"><time datetime="${escape(row.created_at)}" title="${escape(date(row.created_at))}">${escape(new Date(row.created_at).toLocaleTimeString(undefined, {hour: 'numeric', minute: '2-digit'}))}</time>${actions}${row.seen ? '' : `<button type="button" class="small" data-seen="${escape(row.id)}">Mark read</button>`}</div>
  </li>`;
}

async function renderTimeline() {
  const params = new URLSearchParams();
  if (timelineFilter) params.set('kind', timelineFilter);
  if (timelineUnseen) params.set('unseen', '1');
  const data = await api('inbox?' + params);
  updateUnreadBadge(data.unread.total);
  lastUnread = data.unread.total;
  const chip = (kind, label) => `<button type="button" class="chip" data-timeline-filter="${kind}" aria-pressed="${timelineFilter === kind}">${label}${kind ? (data.unread[kind] ? ` <span class="count">${data.unread[kind]} new</span>` : '') : data.unread.total ? ` <span class="count">${data.unread.total} new</span>` : ''}</button>`;
  const notifying = notificationsOn();
  const days = new Map();
  for (const row of data.events) {
    const day = new Date(row.created_at).toLocaleDateString(undefined, {weekday: 'long', month: 'long', day: 'numeric'});
    days.set(day, [...(days.get(day) || []), row]);
  }
  $('content').innerHTML = `
    <div class="toolbar">
      <div class="filters" role="group" aria-label="Filter changes">${chip('', 'All')}${chip('content_changed', 'Content')}${chip('rights_drift', 'Rights')}${chip('link_rot', 'Broken links')}${chip('collection_problem', 'Problems')}</div>
      <div class="actions">
        <label class="check-inline"><input type="checkbox" id="timeline-unseen"${timelineUnseen ? ' checked' : ''}> Unread only</label>
        <button type="button" class="small" id="notify-toggle" aria-pressed="${notifying}">${icon('bell')}${notifying ? 'Notifications on' : 'Notify me'}</button>
        <button type="button" class="secondary small" id="mark-all"${data.unread.total ? '' : ' disabled'}>${icon('check')}Mark all read</button>
      </div>
    </div>
    ${data.events.length ? `<div class="timeline">${[...days].map(([day, rows]) => `<section class="day"><h4>${escape(day)}</h4><ol>${rows.map(changeCard).join('')}</ol></section>`).join('')}</div>`
      : empty(timelineFilter || timelineUnseen ? 'Nothing here.' : 'No changes recorded yet.',
        timelineFilter || timelineUnseen ? 'Try another filter or include read changes.' : 'Watch a source to re-collect it every hour while Proofpage runs. Content edits, publisher rights changes, broken links, and collection problems will appear here.',
        timelineFilter || timelineUnseen ? '' : `<button type="button" class="primary" data-go="sources">${icon('eye')}Choose sources to watch</button>`, 'history')}`;
  $('timeline-unseen').onchange = event => { timelineUnseen = event.target.checked; action(renderTimeline); };
  $('mark-all').onclick = () => action(async () => { await api('inbox-seen', {all: true}); await refresh(); }, $('mark-all'));
  $('notify-toggle').onclick = () => action(toggleNotifications, $('notify-toggle'));
}

// ---------- Notifications (opt-in, while Proofpage is open) ----------
function notificationsOn() {
  try { return localStorage.getItem('proofpage-notify') === '1' && 'Notification' in window && Notification.permission === 'granted'; } catch { return false; }
}

async function toggleNotifications() {
  if (notificationsOn()) {
    localStorage.setItem('proofpage-notify', '0');
    notice('Notifications are off.');
  } else {
    if (!('Notification' in window)) throw new Error('This browser does not support notifications.');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Notifications were not allowed. You can change this in your browser’s site settings.');
    localStorage.setItem('proofpage-notify', '1');
    notice('You’ll be notified about new changes while this workspace is open.');
  }
  startNotifications();
  if (view === 'timeline') await renderTimeline();
}

function startNotifications() {
  clearInterval(notifyTimer);
  if (!notificationsOn()) return;
  notifyTimer = setInterval(() => checkNotifications().catch(() => {}), 60000);
}

async function checkNotifications() {
  const data = await api('inbox?unseen=1');
  const total = data.unread.total;
  updateUnreadBadge(total);
  if (lastUnread !== null && total > lastUnread && data.events[0]) {
    const latest = data.events[0];
    new Notification(`Proofpage: ${pluralize(total - lastUnread, 'new change')}`, {body: `${(CHANGE_KINDS[latest.kind] || [latest.kind])[0]} — ${latest.detail.title || latest.detail.source_name || ''}`, tag: 'proofpage-changes'});
  }
  lastUnread = total;
}

// ---------- Revision comparison (evidence drawer) ----------
function numbersHtml(text) {
  let html = '', last = 0;
  for (const match of text.matchAll(NUMBER_RE)) {
    html += escape(text.slice(last, match.index)) + `<b class="num">${escape(match[0])}</b>`;
    last = match.index + match[0].length;
  }
  return html + escape(text.slice(last));
}

function wordsHtml(words, side) {
  return words.map(([op, text]) => op === 'equal' ? escape(text)
    : op === 'delete' ? (side === 'new' ? '' : `<del>${numbersHtml(text)}</del>`)
      : (side === 'old' ? '' : `<ins>${numbersHtml(text)}</ins>`)).join('');
}

function unchangedHtml(lines, position, row) {
  const context = 2;
  if (lines.length <= context * 2 + 1) return lines.map(row).join('');
  const head = position === 'first' ? [] : lines.slice(0, context);
  const tail = position === 'last' ? [] : lines.slice(-context);
  const hidden = lines.slice(head.length, lines.length - tail.length);
  return head.map(row).join('') + `<details class="unchanged"><summary>${pluralize(hidden.length, 'unchanged line')}</summary>${hidden.map(row).join('')}</details>` + tail.map(row).join('');
}

function diffHtml(result, mode) {
  const blocks = result.blocks;
  if (result.stats.identical) return '<p class="callout">' + icon('info') + '<span>These versions have the same text. Their hashes differ because other captured fields changed.</span></p>';
  const position = index => index === 0 ? 'first' : index === blocks.length - 1 ? 'last' : 'middle';
  if (mode === 'side') {
    const row = (left, right, leftClass = '', rightClass = '') => `<div class="diff-row"><div class="diff-cell ${leftClass}">${left}</div><div class="diff-cell ${rightClass}">${right}</div></div>`;
    return `<div class="diff side"><div class="diff-row diff-labels"><div>Before · ${escape(date(result.from.captured_at))}</div><div>After · ${escape(date(result.to.captured_at))}</div></div>${blocks.map((block, index) => {
      if (block.op === 'equal') return unchangedHtml(block.lines, position(index), line => row(escape(line), escape(line)));
      if (block.op === 'delete') return block.old.split('\n').map(line => row(numbersHtml(line), '', 'del', 'blank')).join('');
      if (block.op === 'insert') return block.new.split('\n').map(line => row('', numbersHtml(line), 'blank', 'ins')).join('');
      return row(wordsHtml(block.words, 'old'), wordsHtml(block.words, 'new'), 'mod', 'mod');
    }).join('')}</div>`;
  }
  const line = (text, kind = '') => `<div class="diff-line ${kind}">${text}</div>`;
  return `<div class="diff inline">${blocks.map((block, index) => {
    if (block.op === 'equal') return unchangedHtml(block.lines, position(index), text => line(escape(text)));
    if (block.op === 'delete') return block.old.split('\n').map(text => line(numbersHtml(text), 'del')).join('');
    if (block.op === 'insert') return block.new.split('\n').map(text => line(numbersHtml(text), 'ins')).join('');
    return line(wordsHtml(block.words, 'both'), 'mod');
  }).join('')}</div>`;
}

async function loadVersions(options = {}) {
  const itemId = evidenceContext.id;
  const data = await api(`items/${itemId}/timeline`);
  const versions = data.versions;
  const to = versions.some(v => v.revision_id === options.to) ? options.to : versions[0]?.revision_id;
  const index = versions.findIndex(v => v.revision_id === to);
  const from = versions.some(v => v.revision_id === options.from) ? options.from : versions[index + 1]?.revision_id;
  let mode = 'inline';
  try { mode = localStorage.getItem('proofpage-diff-mode') || 'inline'; } catch {}
  versionsState = {itemId, data, from, to, mode, summaries: {}};
  await renderVersions();
}

async function renderVersions() {
  const {itemId, data, from, to, mode} = versionsState;
  const versions = data.versions;
  const panel = $('panel-versions');
  if (!panel || evidenceContext.id !== itemId) return;
  const option = (v, selected) => `<option value="${escape(v.revision_id)}"${v.revision_id === selected ? ' selected' : ''}>${escape(date(v.captured_at))}${v.current ? ' (current)' : ''}</option>`;
  const changes = data.changes.filter(row => row.kind !== 'content_changed');
  panel.innerHTML = `
    <p class="muted">Each change creates a new immutable revision. Choose a version to compare it with the one before it, or open it to review or revoke that exact version.</p>
    <div class="versions">${versions.map(v => `<div class="version${v.revision_id === to ? ' current' : ''}">
      <button type="button" class="version-pick" data-pick="${escape(v.revision_id)}" aria-pressed="${v.revision_id === to}"><b>${escape(date(v.captured_at))}</b><small>${escape(v.summary)}</small></button>
      <span class="actions">${v.current ? '<span class="pill tone-accent">Current</span>' : ''}<code class="seal">${escape(v.hash.slice(0, 4))}·${escape(v.hash.slice(4, 8))}</code><button type="button" class="small" data-revision="${escape(v.revision_id)}" data-record="${escape(itemId)}">Open</button></span>
    </div>`).join('')}</div>
    ${versions.length > 1 && from ? `
      <div class="section-label">Comparison</div>
      <div class="diff-toolbar">
        <label>From<select id="diff-from">${versions.map(v => option(v, from)).join('')}</select></label>
        <label>To<select id="diff-to">${versions.map(v => option(v, to)).join('')}</select></label>
        <div class="segmented" role="group" aria-label="Comparison layout">
          <button type="button" data-diff-mode="inline" aria-pressed="${mode === 'inline'}" title="Inline" aria-label="Inline">${icon('list')}</button>
          <button type="button" data-diff-mode="side" aria-pressed="${mode === 'side'}" title="Side by side" aria-label="Side by side">${icon('columns')}</button>
        </div>
      </div>
      <div id="diff-view"><div class="skeleton"></div></div>`
      : '<p class="callout">' + icon('info') + '<span>Only one version so far. Watch this source and Proofpage records a new version whenever the page text changes.</span></p>'}
    ${changes.length ? `<div class="section-label">Other recorded changes</div><div class="rows">${changes.map(row => `<div class="row"><div><h3>${escape((CHANGE_KINDS[row.kind] || [row.kind])[0])}</h3><p>${escape(row.detail.summary || '')}</p></div><time class="muted">${escape(date(row.created_at))}</time></div>`).join('')}</div>` : ''}`;
  if (!(versions.length > 1 && from)) return;
  $('diff-from').onchange = event => { versionsState.from = event.target.value; action(renderVersions); };
  $('diff-to').onchange = event => { versionsState.to = event.target.value; action(renderVersions); };
  const result = await api(`diff?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
  if (versionsState.from !== from || versionsState.to !== to || !$('diff-view')) return;
  $('diff-view').innerHTML = `<div class="diff-summary"><span>${escape(result.summary)}</span>${changeStats(result.stats)}</div>
    ${result.stats.identical ? '' : `<div id="model-summary">${modelSummaryHtml()}</div>`}
    ${diffHtml(result, mode)}
    <p class="muted">Lexical comparison of stored text: it shows what changed, not whether the change matters.</p>`;
}

function modelSummaryHtml() {
  const {data, from, to, summaries} = versionsState;
  const saved = summaries[from + ':' + to];
  if (saved) {
    return `<section class="model-summary" aria-label="Model-written summary">
      <div class="change-head"><span class="pill tone-warn">Unreviewed · written by ${escape(saved.model)}</span>${saved.truncated ? '<span class="muted">Long change; only part was sent.</span>' : ''}</div>
      <p>${escape(saved.summary)}</p>
      ${saved.notable.length ? `<ul>${saved.notable.map(item => `<li>${escape(item)}</li>`).join('')}</ul>` : ''}
      <p class="muted">${escape(saved.note)}</p>
    </section>`;
  }
  if (!data.model?.configured) {
    return `<p class="muted model-summary-hint">${icon('sparkle', 'icon-sm')} Want a plain-language summary? ${escape(data.model?.detail || 'Configure a model to enable it.')}</p>`;
  }
  return `<div class="model-summary-hint"><button type="button" class="small" id="summarize-change">${icon('sparkle')}Summarize with ${escape(data.model.model)}</button>
    <span class="muted">Sends only the changed lines (up to 16,000 characters) to your configured model when you click. Review personal information first; the result is unreviewed.</span></div>`;
}

async function summarizeChange(button) {
  const {from, to} = versionsState;
  const result = await api('change-summary', {from_revision: from, to_revision: to});
  versionsState.summaries[from + ':' + to] = result;
  if (versionsState.from === from && versionsState.to === to && $('model-summary')) $('model-summary').innerHTML = modelSummaryHtml();
}

document.addEventListener('click', event => {
  const b = event.target.closest('button');
  if (!b) return;
  if (b.dataset.timelineFilter !== undefined) { timelineFilter = b.dataset.timelineFilter; action(renderTimeline); }
  if (b.dataset.seen) action(async () => { await api('inbox-seen', {ids: [b.dataset.seen]}); await refresh(); }, b);
  if (b.dataset.change && !b.dataset.seen) api('inbox-seen', {ids: [b.dataset.change]}).catch(() => {});
  if (b.dataset.compare) openItem(b.dataset.compare, {tab: 'versions', from: b.dataset.from, to: b.dataset.to});
  if (b.dataset.openChange) openItem(b.dataset.openChange);
  if (b.dataset.pick && versionsState) {
    const versions = versionsState.data.versions;
    const index = versions.findIndex(v => v.revision_id === b.dataset.pick);
    versionsState.to = versions[index + 1] ? b.dataset.pick : versions[index - 1]?.revision_id || b.dataset.pick;
    versionsState.from = versions[index + 1] ? versions[index + 1].revision_id : b.dataset.pick;
    action(renderVersions);
  }
  if (b.id === 'summarize-change' && versionsState) action(() => summarizeChange(b), b);
  if (b.dataset.diffMode && versionsState) {
    versionsState.mode = b.dataset.diffMode;
    try { localStorage.setItem('proofpage-diff-mode', versionsState.mode); } catch {}
    action(renderVersions);
  }
});
