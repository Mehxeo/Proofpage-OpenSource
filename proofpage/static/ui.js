// Shared interface helpers: API access, feedback, components, routing, theme, and the command palette.
// Classic script loaded before app.js and workbench.js; they share these globals.
let token, hostingMode = 'local';

const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const date = value => value ? new Date(value).toLocaleString() : 'Not supplied';
const pluralize = (count, word, plural = word + 's') => `${count} ${count === 1 ? word : plural}`;

function relativeTime(value) {
  if (!value) return 'Not supplied';
  const seconds = (Date.now() - new Date(value).getTime()) / 1000;
  if (!Number.isFinite(seconds)) return 'Not supplied';
  const units = [[60, 'second', 1], [3600, 'minute', 60], [86400, 'hour', 3600], [604800, 'day', 86400], [2629800, 'week', 604800], [31557600, 'month', 2629800], [Infinity, 'year', 31557600]];
  const format = new Intl.RelativeTimeFormat(undefined, {numeric: 'auto'});
  for (const [limit, unit, size] of units) {
    if (Math.abs(seconds) < limit) return format.format(-Math.round(seconds / size), unit);
  }
}

async function api(path, data) {
  const response = await fetch('/api/' + path, {
    method: data === undefined ? 'GET' : 'POST',
    headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed.');
  return value;
}

async function download(path, filename) {
  const response = await fetch('/api/' + path, {headers: {Authorization: 'Bearer ' + token}});
  if (!response.ok) throw new Error((await response.json()).error);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------- Feedback ----------
function toast(text, tone = 'ok') {
  const element = document.createElement('div');
  element.className = 'toast' + (tone === 'error' ? ' error' : '');
  element.setAttribute('role', tone === 'error' ? 'alert' : 'status');
  element.innerHTML = `${icon(tone === 'error' ? 'alert' : 'check')}<p></p><button type="button" aria-label="Dismiss">${icon('x', 'icon-sm')}</button>`;
  element.querySelector('p').textContent = text;
  element.querySelector('button').onclick = () => element.remove();
  $('toasts').append(element);
  setTimeout(() => element.remove(), tone === 'error' ? 9000 : 5000);
}

function notice(text, error = false) { toast(text, error ? 'error' : 'ok'); }

async function action(fn, button) {
  if (button) button.disabled = true;
  document.querySelectorAll('.dialog-error').forEach(element => element.remove());
  try {
    await fn();
  } catch (error) {
    const dialog = [...document.querySelectorAll('dialog[open]')].filter(d => d.id !== 'palette').at(-1);
    if (dialog) {
      const message = document.createElement('p');
      message.className = 'dialog-error';
      message.setAttribute('role', 'alert');
      message.textContent = error.message;
      (dialog.querySelector('.drawer-foot') || dialog.querySelector('.drawer-body') || dialog).append(message);
    } else {
      notice(error.message, true);
    }
  } finally {
    if (button) button.disabled = false;
  }
}

// ---------- Components ----------
function icon(name, extra = '') {
  return `<svg class="icon ${extra}" aria-hidden="true" focusable="false"><use href="/icons.svg#${name}"></use></svg>`;
}

function seal(hash, label = 'SHA-256') {
  if (!hash) return '';
  return `<button type="button" class="seal" data-copy="${escape(hash)}" title="${escape(label)} ${escape(hash)} · click to copy" aria-label="Copy ${escape(label)} ${escape(hash)}">${icon('seal')}${escape(hash.slice(0, 4))}·${escape(hash.slice(4, 8))}</button>`;
}

const STATES = {
  ready: ['Ready', '', 'Configured. Nothing has been collected yet.'],
  available: ['Available', 'ok', 'The last capture confirmed public page content.'],
  running: ['Collecting', 'info live', 'A collection is in progress.'],
  queued: ['Queued', 'info', 'Waiting for its turn or for a host cooldown.'],
  complete: ['Complete', 'ok', 'Finished. Check outcomes for any pages that were not captured.'],
  partial: ['Partial', 'warn', 'Some pages were captured; others were not. Outcomes list each page.'],
  discovery: ['Links found', 'info', 'A feed or sitemap was found. Links were listed; no article text was inferred.'],
  restricted: ['Robots excluded', 'warn', 'The site robots policy excludes this page, so Proofpage did not collect it.'],
  rate_limited: ['Cooling down', 'warn', 'The site asked collectors to slow down. Proofpage will wait before retrying.'],
  policy_unavailable: ['Policy unavailable', 'warn', 'The robots policy could not be read, so collection paused.'],
  authentication_required: ['Login required', 'danger', 'This page needs a login. Proofpage does not bypass logins.'],
  access_denied: ['Access denied', 'danger', 'The site refused access. Previous evidence is kept.'],
  challenge_required: ['Bot challenge', 'danger', 'The site showed a human-verification challenge. Proofpage does not solve CAPTCHAs.'],
  http_error: ['HTTP error', 'danger', 'The site returned an error. Previous evidence is kept.'],
  insufficient_content: ['Too little text', 'warn', 'The page had too little readable text to keep.'],
  unsupported_format: ['Unsupported format', 'warn', 'This content type is not collected yet.'],
  failed: ['Failed', 'danger', 'The collection did not complete. See the detail for why.'],
  cancelled: ['Cancelled', '', 'No further requests will start.'],
  interrupted: ['Interrupted', 'warn', 'Stopped when Proofpage closed. It can be started again.'],
  paused: ['Paused', '', 'Paused. Resume when you are ready.'],
  settling: ['Settling', 'info', 'Waiting for the file to finish changing.'],
  imported: ['Imported', 'ok', 'Imported into your library.'],
  draft: ['Draft', 'info', 'Not reviewed yet.'],
  approved: ['Approved', 'ok', 'Reviewed and approved for a dataset.'],
  rejected: ['Rejected', 'danger', 'Rejected during review.'],
  revoked: ['Revoked', 'danger', 'Approval was withdrawn. Exports that include it are blocked.'],
};

function stateInfo(state) {
  const known = STATES[state];
  const fallback = String(state || 'unknown').replaceAll('_', ' ');
  return known ? {label: known[0], tone: known[1], help: known[2]} : {label: fallback[0].toUpperCase() + fallback.slice(1), tone: '', help: ''};
}

function statusPill(state) {
  const info = stateInfo(state);
  const tones = info.tone.split(' ').filter(Boolean);
  const classes = ['pill', ...tones.map((tone, index) => index ? tone : 'tone-' + tone)].join(' ');
  return `<span class="${classes}"${info.help ? ` title="${escape(info.help)}"` : ''}>${escape(info.label)}</span>`;
}

function empty(title, description, actions = '', mark = 'library') {
  return `<div class="empty"><div class="mark">${icon(mark)}</div><h2>${title}</h2><p>${description}</p>${actions ? `<div class="actions">${actions}</div>` : ''}</div>`;
}

function hostname(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url || ''; }
}

function highlight(text, terms) {
  let html = escape(text);
  for (const term of terms.filter(t => t.length > 1)) {
    html = html.replace(new RegExp('(' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi'), '<mark>$1</mark>');
  }
  return html;
}

function openModal(title, html) {
  if ($('evidence-dialog').open) $('evidence-dialog').close();
  $('work-title').textContent = title;
  $('work-content').innerHTML = html;
  if (!$('work-dialog').open) $('work-dialog').showModal();
}

// ---------- Routing ----------
// Routes: #/<view> and #/item/<id>. Navigation pushes history so the back button works.
let openedItemFromApp = false;

function parseRoute() {
  const match = location.hash.match(/^#\/([a-z]+)(?:\/([\w-]+))?/);
  return match ? {name: match[1], id: match[2]} : {name: 'library'};
}

function routeView(name) {
  if (name === 'item') return 'library';
  return document.querySelector(`[data-view="${name}"]`) ? name : 'library';
}

function navigate(next) {
  view = next;
  if (location.hash !== '#/' + next) history.pushState(null, '', '#/' + next);
}

function openItem(id) {
  openedItemFromApp = true;
  history.pushState(null, '', '#/item/' + id);
  action(() => showEvidence(id));
}

async function applyRoute(initial = false) {
  const route = parseRoute();
  const next = routeView(route.name);
  const changed = initial || next !== view;
  view = next;
  if (changed) await refresh();
  if (route.name === 'item' && route.id) {
    await showEvidence(route.id);
  } else if ($('evidence-dialog').open) {
    $('evidence-dialog').close();
  }
}

window.addEventListener('hashchange', () => action(() => applyRoute()));

// ---------- Theme ----------
function currentTheme() {
  return document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
}

function applyThemeButton() {
  const dark = currentTheme() === 'dark';
  $('theme-toggle').innerHTML = icon(dark ? 'sun' : 'moon');
  $('theme-toggle').setAttribute('aria-label', dark ? 'Use light theme' : 'Use dark theme');
  $('theme-toggle').title = dark ? 'Use light theme' : 'Use dark theme';
}

function toggleTheme() {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('proofpage-theme', next); } catch {}
  applyThemeButton();
}

(() => {
  try {
    const saved = localStorage.getItem('proofpage-theme');
    if (saved === 'light' || saved === 'dark') document.documentElement.dataset.theme = saved;
  } catch {}
})();

// ---------- Command palette ----------
const paletteViews = () => [...document.querySelectorAll('.sidebar [data-view]')].map(button => ({
  label: button.querySelector('.nav-text')?.textContent || button.textContent.trim(),
  icon: button.dataset.icon || 'arrow-right',
  run: () => { navigate(button.dataset.view); return refresh(); },
}));
const paletteActions = () => [
  {label: 'Add a web source', icon: 'plus', run: () => $('source-dialog').showModal()},
  {label: 'Import files', icon: 'upload', run: () => $('import-open').click()},
  {label: 'Collect multiple pages', icon: 'layers', run: () => openCrawl()},
  {label: currentTheme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme', icon: currentTheme() === 'dark' ? 'sun' : 'moon', run: toggleTheme},
];
let paletteEntries = [], paletteIndex = 0, paletteRequest = 0;

function openPalette() {
  $('palette-input').value = '';
  renderPalette([]);
  if (!$('palette').open) $('palette').showModal();
  $('palette-input').focus();
}

function renderPalette(items) {
  const query = $('palette-input').value.trim().toLowerCase();
  const matches = entry => !query || entry.label.toLowerCase().includes(query);
  const groups = [
    ['Evidence', items.slice(0, 8).map(item => ({label: item.title, detail: `${item.source_name} · ${relativeTime(item.captured_at)}`, icon: item.kind === 'document' ? 'file' : 'message', run: () => { $('palette').close(); openItem(item.id); }}))],
    ['Go to', paletteViews().filter(matches)],
    ['Actions', paletteActions().filter(matches)],
  ];
  paletteEntries = [];
  $('palette-results').innerHTML = groups.filter(([, entries]) => entries.length).map(([title, entries]) => `<div class="palette-group">${title}</div>` + entries.map(entry => {
    paletteEntries.push(entry);
    const index = paletteEntries.length - 1;
    return `<button type="button" class="palette-item" role="option" id="palette-option-${index}" data-palette-index="${index}">${icon(entry.icon)}<span>${escape(entry.label)}${entry.detail ? `<small>${escape(entry.detail)}</small>` : ''}</span></button>`;
  }).join('')).join('') || '<p class="muted palette-group">No matches.</p>';
  paletteIndex = 0;
  markPalette();
}

function markPalette() {
  document.querySelectorAll('.palette-item').forEach(element => element.setAttribute('aria-selected', String(Number(element.dataset.paletteIndex) === paletteIndex)));
  const active = $('palette-option-' + paletteIndex);
  if (active) {
    active.scrollIntoView({block: 'nearest'});
    $('palette-input').setAttribute('aria-activedescendant', active.id);
  }
}

function runPalette(index) {
  const entry = paletteEntries[index];
  if (!entry) return;
  if ($('palette').open) $('palette').close();
  action(async () => entry.run());
}

let paletteTimer;
function paletteSearch() {
  clearTimeout(paletteTimer);
  paletteTimer = setTimeout(() => action(async () => {
    const query = $('palette-input').value.trim();
    const request = ++paletteRequest;
    const items = query ? (await api('state?q=' + encodeURIComponent(query))).items : [];
    if (request === paletteRequest) renderPalette(items);
  }), 140);
}

// ---------- Global wiring ----------
document.addEventListener('keydown', event => {
  const typing = event.target.closest('input, textarea, select, [contenteditable]');
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    openPalette();
  } else if (event.key === '/' && !typing && !document.querySelector('dialog[open]')) {
    event.preventDefault();
    openPalette();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  applyThemeButton();
  $('theme-toggle').onclick = toggleTheme;
  $('palette-open').onclick = openPalette;
  $('palette-input').addEventListener('input', paletteSearch);
  $('palette-input').addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      paletteIndex = (paletteIndex + (event.key === 'ArrowDown' ? 1 : -1) + paletteEntries.length) % Math.max(1, paletteEntries.length);
      markPalette();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      runPalette(paletteIndex);
    }
  });
  $('palette').addEventListener('click', event => {
    if (event.target === $('palette')) return $('palette').close();
    const item = event.target.closest('[data-palette-index]');
    if (item) runPalette(Number(item.dataset.paletteIndex));
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyThemeButton);
});

document.addEventListener('click', event => {
  const copy = event.target.closest('[data-copy]');
  if (copy) {
    event.stopPropagation();
    navigator.clipboard.writeText(copy.dataset.copy).then(() => toast('Copied ' + copy.dataset.copy.slice(0, 16) + (copy.dataset.copy.length > 16 ? '…' : '')), () => toast('Clipboard access is unavailable. Select and copy the value instead.', 'error'));
  }
  // Clicking a modal's backdrop closes it.
  if (event.target instanceof HTMLDialogElement && event.target.open && event.target.id !== 'palette') {
    const box = event.target.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) event.target.close();
  }
}, true);
