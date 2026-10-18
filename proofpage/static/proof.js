// Proof Receipts: the evidence drawer's Proof tab, the Settings view, and proof downloads.
const PROOF_STATES = {
  anchored: ['Signed · anchored', 'ok', 'A signed receipt exists and its batch has an independent timestamp.'],
  anchoring: ['Signed · anchoring', 'info', 'A signed receipt exists; its timestamp is pending or needs a retry.'],
  signed: ['Signed receipt', 'ok', 'Proofpage signed a receipt for this capture with the workspace key.'],
  none: ['No receipt', '', 'Captured before Proof Receipts, or supplied from an archive.'],
};
const ANCHOR_STATES = {complete: ['Timestamped', 'ok'], submitted: ['Submitted', 'info'], submitting: ['Submitting', 'info'], failed: ['Failed', 'danger'], off: ['Off', '']};

function proofPill(state) {
  const [label, tone, help] = PROOF_STATES[state] || PROOF_STATES.none;
  return `<span class="pill${tone ? ' tone-' + tone : ''}" title="${escape(help)}">${icon(state === 'none' ? 'info' : 'seal', 'icon-sm')}${escape(label)}</span>`;
}

function anchorPill(state, label) {
  const [text, tone] = ANCHOR_STATES[state] || ANCHOR_STATES.off;
  return `<span class="pill${tone ? ' tone-' + tone : ''}">${escape(label)}: ${escape(text)}</span>`;
}

function anchorSummary(anchor) {
  if (!anchor) return '<span class="muted">Not anchored yet</span>';
  return [anchor.tsa_state !== 'off' ? anchorPill(anchor.tsa_state, 'RFC 3161') : '', anchor.ots_state !== 'off' ? anchorPill(anchor.ots_state, 'OpenTimestamps') : ''].join('')
    + (anchor.tsa_time ? `<span class="muted">${escape(date(anchor.tsa_time))}</span>` : '');
}

function proofPanel(proof, item) {
  const web = item.source_kind ? item.source_kind === 'web' : !!JSON.parse(item.metadata || '{}').url;
  const wacz = web ? `<button type="button" class="secondary small" data-wacz="${escape(item.source_id)}" data-wacz-name="${escape(item.source_name)}">${icon('download')}Export source as WACZ</button>` : '';
  if (!proof || proof.state === 'none') {
    return `<p class="callout">${icon('info')}<span>${web ? 'No signed receipt for this revision yet. Proofpage signs a receipt for every capture made with Proof Receipts; collect the source again to get one.' : 'Receipts cover web captures. This record came from an archive you supplied.'}</span></p>${wacz ? `<div class="actions">${wacz}</div>` : ''}`;
  }
  return `<div class="proof-head">${proofPill(proof.state)}<span class="muted">Workspace key</span><button type="button" class="seal" data-copy="${escape(proof.fingerprint)}" title="Key fingerprint ${escape(proof.fingerprint)} · click to copy">${icon('key')}${escape(proof.fingerprint.slice(0, 4))}·${escape(proof.fingerprint.slice(4, 8))}</button></div>
    <p>Every capture gets a receipt signed with this workspace’s Ed25519 key and chained to the receipt before it, so signature and chain checks can detect edits and missing links. Detecting a truncated tail requires a previously trusted chain head or external anchor.${proof.state === 'signed' ? ' Turn on timestamp anchoring in Settings to add independent evidence of when receipts existed.' : ''}</p>
    <div class="section-label">Receipts · ${proof.receipts.length}</div>
    <div class="rows">${proof.receipts.map(receipt => `<div class="row"><div><h3>Receipt ${receipt.seq} · ${escape(date(receipt.requested_at))}</h3>
      <p class="mono-ish">${escape(receipt.url)}</p><div class="chips start">${statusPill(receipt.status === 200 ? 'available' : 'http_error').replace(/>[^<]*</, `>HTTP ${receipt.status}<`)}${receipt.exact_bytes ? '<span class="pill tone-ok">Exact bytes</span>' : '<span class="pill">Reconstructed text</span>'}${anchorSummary(receipt.anchor)}</div></div>${seal(receipt.hash, 'Receipt SHA-256')}</div>`).join('')}</div>
    <div class="actions"><button type="button" class="primary small" data-proof-bundle="${escape(item.current_revision)}">${icon('download')}Download proof bundle</button>${wacz}</div>
    <p class="muted">Check a bundle anywhere with <code>python3 verify_proof.py</code> — Python 3 is required, with no extra packages. A receipt attests what this workspace observed; TLS cannot prove what a server sent.</p>`;
}

// ---------- Settings ----------
async function renderSettings() {
  const data = await api('receipts');
  const s = data.settings;
  const local = hostingMode === 'local';
  $('content').innerHTML = `
    ${local ? `<section class="panel"><h3>Browser companion</h3><p>Save reviewed pages directly from Chrome. Open the companion, enter this app’s port and a pairing code once. Reconnect after restarting Proofpage. The connection can only import pages.</p><div class="actions"><button id="companion-code">Connect browser</button><button id="companion-revoke" class="secondary">Disconnect browser</button></div><button type="button" id="attention-notifications" class="secondary">Toggle attention notifications</button><p id="companion-result" role="status"></p></section>` : ''}
    <section class="panel">
      <div class="panel-head"><div><h3>Receipt signing key</h3><p>Proofpage signs a receipt for every capture with this Ed25519 key. It stays in this workspace’s database and is included in backups — keep backups private.</p></div><span class="pill tone-ok">${pluralize(data.receipts, 'receipt')}</span></div>
      <dl class="meta-grid">
        <dt>Fingerprint</dt><dd><code>${escape(data.key.fingerprint)}</code> <button type="button" class="small" data-copy="${escape(data.key.fingerprint)}">${icon('copy')}Copy</button></dd>
        <dt>Public key</dt><dd><code>${escape(data.key.public_key)}</code> <button type="button" class="small" data-copy="${escape(data.key.public_key)}">${icon('copy')}Copy</button></dd>
        <dt>Created</dt><dd>${escape(date(data.key.created_at))}</dd>
        <dt>Not yet anchored</dt><dd>${pluralize(data.unanchored, 'receipt')}</dd>
      </dl>
      <div class="actions"><button type="button" class="secondary" id="verify-chain">${icon('shield')}Check chain integrity</button></div>
      <div id="chain-result"></div>
    </section>
    ${local ? `<form class="panel" id="anchor-form">
      <div class="panel-head"><div><h3>Timestamp anchoring</h3><p>Once a day, Proofpage combines new receipts into one Merkle root and asks the services you choose to timestamp its SHA-256 digest. Only that digest is sent — never page content, URLs, or receipts.</p></div><span class="pill">${s.anchor_tsa_url || s.anchor_ots === '1' ? 'On' : 'Off by default'}</span></div>
      <label>RFC 3161 timestamp authority URL<input name="anchor_tsa_url" placeholder="https://freetsa.org/tsr" value="${escape(s.anchor_tsa_url)}"></label>
      <label><input type="checkbox" name="anchor_ots"${s.anchor_ots === '1' ? ' checked' : ''}> Also submit to OpenTimestamps (anchored in Bitcoin; completes after a few hours)</label>
      <label>OpenTimestamps calendar<input name="anchor_ots_calendar" value="${escape(s.anchor_ots_calendar)}"></label>
      <div class="actions"><button class="primary">${icon('check')}Save anchoring settings</button><button type="button" class="secondary" id="anchor-now"${s.anchor_tsa_url || s.anchor_ots === '1' ? '' : ' disabled'}>${icon('clock')}Anchor now</button></div>
    </form>` : `<p class="callout">${icon('info')}<span>Timestamp anchoring runs in the local edition, where you choose the services it contacts. Receipts are still signed here.</span></p>`}
    <div class="section-label">Anchors · ${data.anchors.length}</div>
    ${data.anchors.length ? `<div class="rows">${data.anchors.map(anchor => `<div class="row"><div><h3>${escape(date(anchor.created_at))} · receipts ${anchor.first_seq}–${anchor.last_seq}</h3>
      <p>${escape([anchor.tsa_detail, anchor.ots_detail].filter(Boolean).join(' · ') || 'Waiting for the first submission.')}</p><div class="chips start">${anchorSummary(anchor)}</div></div>${seal(anchor.root, 'Merkle root')}</div>`).join('')}</div>`
      : '<p class="muted">No anchors yet. Anchoring is optional; receipts are signed and chained either way.</p>'}
    <section class="panel">
      <h3>Verify anywhere</h3>
      <p>Proof bundles and WACZ archives include a standalone verifier. Anyone can check them offline with Python, or check signatures with OpenSSL.</p>
      <pre>python3 verify_proof.py              # inside an extracted proof bundle
proofpage verify proof-bundle.zip
proofpage verify archive.wacz
proofpage receipts                    # re-check this workspace’s receipt chain</pre>
    </section>`;
  $('verify-chain').onclick = () => action(async () => {
    const result = await api('receipts-verify', {});
    $('chain-result').innerHTML = result.ok
      ? `<p class="screening clear">${icon('check')}<span>All ${pluralize(result.receipts, 'receipt')} verified: signatures, hashes, and chain links. Head ${escape((result.head || '').slice(0, 16))}…</span></p>`
      : `<p class="screening">${icon('alert')}<span>${escape(result.problems.join(' '))}</span></p>`;
  }, $('verify-chain'));
  if (!local) return;
  $('attention-notifications').onclick = () => action(toggleNotifications, $('attention-notifications'));
  $('companion-code').onclick = () => action(async () => {
    const result = await api('companion-code', {});
    $('companion-result').textContent = `Port ${result.port} · Code ${result.code} · Valid for 5 minutes. Enter this only in the Proofpage companion.`;
  }, $('companion-code'));
  $('companion-revoke').onclick = () => action(async () => {
    await api('companion-revoke', {});
    $('companion-result').textContent = 'Browser disconnected. Create a new code to reconnect.';
  }, $('companion-revoke'));
  $('anchor-form').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target);
    action(async () => {
      await api('anchor-settings', {anchor_tsa_url: form.get('anchor_tsa_url'), anchor_ots: form.has('anchor_ots'), anchor_ots_calendar: form.get('anchor_ots_calendar')});
      notice('Anchoring settings saved.');
      await renderSettings();
    }, event.submitter);
  };
  $('anchor-now').onclick = () => action(async () => {
    const anchor = await api('anchor-now', {});
    notice(anchor ? `Anchored receipts ${anchor.first_seq}–${anchor.last_seq}. ${[anchor.tsa_detail, anchor.ots_detail].filter(Boolean).join(' ')}` : 'Nothing to anchor.');
    await renderSettings();
  }, $('anchor-now'));
}

document.addEventListener('click', event => {
  const b = event.target.closest('button');
  if (!b) return;
  if (b.dataset.proofBundle) action(() => download('proof-bundle/' + b.dataset.proofBundle, `proofpage-proof-${b.dataset.proofBundle.slice(0, 8)}.zip`), b);
  if (b.dataset.wacz) action(() => download('wacz/' + b.dataset.wacz, `${(b.dataset.waczName || 'source').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'source'}.wacz`), b);
});
