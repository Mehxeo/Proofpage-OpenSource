// Claim Check: preview first, explicit collection consent, persisted reports.
let claimDraft = '', claimPreview = null, claimReport = null, claimTimer;
const CLAIM_LABELS = {verified: ['Exact wording', 'ok'], close: ['Close wording · review differences', 'warn'], drifted: ['Found in an older version', 'warn'], not_found: ['Not found', 'danger'], no_source: ['No citation', 'warn'], not_captured: ['Not captured', 'warn'], unreachable: ['Source unreachable', 'danger'], blocked: ['Collection blocked', 'warn'], unavailable: ['Check unavailable', 'warn']};

async function renderClaims() {
  clearTimeout(claimTimer);
  const recent = await api('claim-checks');
  if (view !== 'verify') return;
  $('content').innerHTML = `<section class="panel"><h2>Check an answer before you use it.</h2>
    <p>Paste text with quoted passages and citations. Proofpage checks wording, not factual truth or whether a passage supports the whole argument. Unquoted prose is not checked.</p>
    <label>Answer or document<textarea id="claim-text" rows="8" maxlength="50000" placeholder='“This domain is for use in documentation examples…” https://example.com/'>${escape(claimDraft)}</textarea></label>
    <div class="actions"><button type="button" class="primary" id="claim-preview">Review quotes and sources</button><button type="button" class="secondary" id="claim-example">Load an example</button></div>
    <p class="muted">Preview is local. Nothing is fetched until you choose to collect sources.</p></section>
    <section id="claim-preview-panel"></section><section id="claim-report"></section>
    <section class="panel"><h2>Recent checks</h2>${recent.length ? `<div class="rows">${recent.map(r => `<div class="row"><span>${escape(date(r.created_at))} · ${escape(r.state)}</span><button type="button" class="small" data-claim-open="${escape(r.id)}">Open report</button></div>`).join('')}</div>` : '<p class="muted">Your reports will stay in this workspace.</p>'}</section>`;
  $('claim-text').oninput = e => { claimDraft = e.target.value; claimPreview = null; $('claim-preview-panel').innerHTML = ''; };
  $('claim-preview').onclick = () => action(async () => { claimDraft = $('claim-text').value; claimPreview = await api('claim-preview', {text: claimDraft}); drawClaimPreview(); }, $('claim-preview'));
  $('claim-example').onclick = () => { claimDraft = '“This domain is for use in documentation examples without needing permission.” https://example.com/\n\n“This domain guarantees every AI answer is correct.” https://example.com/'; $('claim-text').value = claimDraft; claimPreview = null; $('claim-preview-panel').innerHTML = ''; };
  if (claimPreview) drawClaimPreview();
  if (claimReport) { drawClaimReport(); pollClaim(); }
}

function drawClaimPreview() {
  const p = claimPreview;
  $('claim-preview-panel').innerHTML = `<section class="panel"><h2>${p.citations.length} quoted passages</h2><p>${escape(p.extraction_note)}</p>
    ${p.citations.map((c, i) => `<div class="claim-preview-row"><blockquote>${escape(c.quote)}</blockquote><label>Source URL for quote ${i+1}<input type="url" data-claim-url="${i}" value="${escape(c.url || '')}" placeholder="https://… (leave empty if uncited)"></label></div>`).join('')}
    ${p.citations.length ? `<label class="check-inline"><input type="checkbox" id="claim-collect"> Collect missing or stale sources (older than 24 hours)</label><p class="muted">Collection visits only the listed public pages, their robots policies and budgeted rights metadata. Site cooldowns and access restrictions apply. Leave unchecked to use saved evidence only.</p><p id="claim-hosts"></p><button type="button" class="primary" id="claim-start">Check ${p.citations.length} quotes</button>` : '<p>No quoted passages found. Use double quotation marks, curly quotation marks, or Markdown blockquotes, followed by a citation in the same paragraph.</p>'}</section>`;
  if (!p.citations.length) return;
  const hosts = () => { const all = [...document.querySelectorAll('[data-claim-url]')].map(e => { try { return new URL(e.value).host; } catch { return ''; } }).filter(Boolean); $('claim-hosts').textContent = 'Sites: ' + ([...new Set(all)].join(', ') || 'No sites paired'); };
  document.querySelectorAll('[data-claim-url]').forEach(input => input.oninput = hosts); hosts();
  $('claim-start').onclick = () => action(async () => {
    const citations = p.citations.map((c, i) => ({...c, url: document.querySelector(`[data-claim-url="${i}"]`).value.trim() || null}));
    claimReport = await api('claim-check', {text: claimDraft, citations, collect_missing: $('claim-collect').checked});
    claimPreview = null; $('claim-preview-panel').innerHTML = ''; drawClaimReport(); pollClaim();
  }, $('claim-start'));
}

function drawClaimReport() {
  if (!$('claim-report') || !claimReport) return;
  const r = claimReport;
  $('claim-report').innerHTML = `<section class="panel"><div class="actions"><h2>Quote report</h2><span class="pill">${escape(r.state)} · ${r.completed}/${r.items.length}</span>${r.state === 'queued' ? '<button type="button" class="secondary" id="claim-cancel">Cancel remaining checks</button>' : ''}</div>
    <p>${escape(r.note)}</p>${r.detail ? `<p role="status">${escape(r.detail)} ${r.next_attempt ? 'Next attempt: '+escape(date(new Date(r.next_attempt*1000).toISOString())) : ''}</p>` : ''}
    <div class="actions">${['markdown','json','html'].map(f => `<button type="button" class="small" data-claim-export="${f}">Download ${f.toUpperCase()}</button>`).join('')}</div>
    <div class="claim-results">${r.items.map(item => {
      const result = item.result, status = result?.status || item.state, label = CLAIM_LABELS[status] || [status, ''];
      return `<article class="card"><div class="card-top"><h3>Quote ${item.position+1}</h3><span class="pill tone-${label[1]}">${escape(label[0])}</span></div><blockquote>${escape(item.quote)}</blockquote>
        <p class="mono-ish">${escape(item.url || 'No source cited')}</p>${result?.excerpt ? `<h4>Captured wording</h4><blockquote>${escape(result.excerpt)}</blockquote>${result.status === 'close' || result.match_kind === 'close' ? `<p class="muted">Similarity ${Math.round(result.score*100)}%. Compare the wording above; even small number or negation changes can matter.</p>` : ''}` : ''}
        ${result?.detail ? `<p>${escape(result.detail)}</p>` : ''}${result?.archived_match ? `<p>Archived wording match: ${escape(result.archived_match)}. Current access was not confirmed.</p>` : ''}
        ${result?.captured_at ? `<p class="muted">Revision saved ${escape(date(result.captured_at))}. ${escape(result.scope)}</p>` : ''}
        <div class="actions">${result?.item_id ? `<button type="button" class="small" data-revision="${escape(result.revision_id)}" data-record="${escape(result.item_id)}">Open captured evidence</button>` : ''}${result?.live_link ? `<a href="${escape(result.live_link)}" target="_blank" rel="noopener noreferrer">Open live passage</a>` : ''}${result?.receipt_hash ? `<button type="button" class="small" data-claim-proof="${escape(result.revision_id)}">Download proof</button>` : ''}</div>
        ${result?.revision_id ? `<details><summary>Optional model review</summary><p class="muted">Sends this quote and up to 1,000 surrounding characters on each side to your configured model. The response remains unreviewed and does not change the wording verdict.</p><button type="button" class="small" data-claim-model="${item.position}">Ask configured model</button>${result.model_review ? `<p><b>Unreviewed · ${escape(result.model_review.assessment)}</b></p><p>${escape(result.model_review.explanation)}</p>` : ''}</details>` : ''}
        ${result?.receipt_hash ? `<p class="muted mono-ish">Receipt ${escape(result.receipt_hash)}</p>` : ''}</article>`;
    }).join('')}</div>
    <details><summary>Annotated document</summary><div class="claim-document">${annotatedClaims(r)}</div></details></section>`;
  if ($('claim-cancel')) $('claim-cancel').onclick = () => action(async () => { claimReport = await api('claim-cancel', {job_id:r.id}); clearTimeout(claimTimer); drawClaimReport(); }, $('claim-cancel'));
}

function pollClaim() {
  clearTimeout(claimTimer);
  if (view !== 'verify' || claimReport?.state !== 'queued') return;
  const id = claimReport.id;
  claimTimer = setTimeout(async () => {
    try { const result = await api('claim-checks/'+id); if (claimReport?.id === id && view === 'verify') { claimReport = result; drawClaimReport(); pollClaim(); } }
    catch (e) { notice('Could not refresh the check. Reopen the report to retry.', true); }
  }, 3000);
}

document.addEventListener('click', event => {
  const b = event.target.closest('button'); if (!b) return;
  if (b.dataset.claimOpen) action(async () => { claimReport = await api('claim-checks/'+b.dataset.claimOpen); drawClaimReport(); pollClaim(); $('claim-report').scrollIntoView({block:'start'}); }, b);
  if (b.dataset.claimExport && claimReport) action(() => download('claim-checks/'+claimReport.id+'?format='+b.dataset.claimExport, 'proofpage-check.'+({markdown:'md',json:'json',html:'html'}[b.dataset.claimExport])), b);
  if (b.dataset.claimModel !== undefined && claimReport) action(async () => { claimReport = await api('claim-model-review', {job_id:claimReport.id, position:Number(b.dataset.claimModel)}); drawClaimReport(); }, b);
  if (b.dataset.claimProof) action(() => download('proof-bundle/'+b.dataset.claimProof, 'proofpage-proof.zip'), b);
});

function annotatedClaims(report) {
  let cursor = 0, output = '';
  for (const item of report.items) {
    if (!Number.isInteger(item.start) || !Number.isInteger(item.end) || item.start < cursor || item.end > report.text.length || report.text.slice(item.start,item.end) !== item.quote) continue;
    output += escape(report.text.slice(cursor,item.start)) + '<mark>' + escape(item.quote) + '</mark><sup> [' + (item.position+1) + ': ' + escape(item.result?.status || item.state) + ']</sup>';
    cursor = item.end;
  }
  return output + escape(report.text.slice(cursor));
}
