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
  const sections = [
    ['general', 'sun', 'General', 'Appearance & preferences'],
    ['connections', 'plug', 'Connections', 'Browser, Docs & assistants'],
    ['integrity', 'seal', 'Evidence integrity', 'Receipts & timestamps'],
    ['about', 'info', local ? 'App & updates' : 'About', 'Version & help'],
  ];
  let section = 'general';
  try { section = localStorage.getItem('proofpage-settings-section') || 'general'; } catch {}
  if (!sections.some(([name]) => name === section)) section = 'general';
  const panel = name => `id="settings-${name}" role="tabpanel" aria-labelledby="settings-tab-${name}"${section === name ? '' : ' hidden'}`;
  const version = document.querySelector('.page-footer > span')?.textContent.split(' · ')[0] || 'Proofpage';
  $('content').innerHTML = `
    <div class="settings-home settings-layout">
      <aside class="settings-rail"><div class="workspace-stamp">${icon('folder')}<div><strong>Your workspace</strong><span>${local ? 'On this computer' : 'Hosted edition'}</span></div></div>
      <div class="settings-tabs" role="tablist" aria-label="Settings sections" aria-orientation="vertical">${sections.map(([name, mark, label, help]) => `<button type="button" role="tab" id="settings-tab-${name}" data-settings-section="${name}" aria-controls="settings-${name}" aria-selected="${section === name}" tabindex="${section === name ? 0 : -1}">${icon(mark)}<span><strong>${label}</strong><small>${help}</small></span></button>`).join('')}</div>
      <a class="settings-guide" href="https://proofpage.app/docs/" target="_blank" rel="noopener noreferrer">Help & documentation ↗</a></aside>
      <div class="settings-panes">
      <section ${panel('general')}>
        <div class="settings-pane-heading"><h2>A space that feels like you.</h2><p>Small adjustments, saved as you go.</p></div>
        <section class="panel appearance-panel"><div class="appearance-preview" aria-hidden="true"><div class="preview-sidebar"><i></i><i></i><i></i></div><div class="preview-canvas"><span></span><div><i></i><i></i><i></i></div></div><span class="preview-seal">p</span></div><div class="appearance-control"><label>Appearance<select id="appearance-theme"><option value="system">Follow system</option><option value="light">Light</option><option value="dark">Dark</option></select></label><p>Follow your device, or choose a look for this browser.</p><p id="appearance-status" class="preference-status" role="status" aria-live="polite"></p></div></section>
        ${local ? `<section class="panel preference-row"><div class="preference-icon">${icon('bell')}</div><div><h3>When a source needs you</h3><p>Optional browser notifications for collection that needs attention.</p></div><button type="button" id="attention-notifications" class="secondary">${notificationsOn() ? 'Turn notifications off' : 'Turn notifications on'}</button></section>` : ''}
        <section class="panel personal-context-link"><div class="preference-icon">${icon('file')}</div><div><h3>Personalization starts with your sources.</h3><p>Review your business facts and writing examples before sharing them with an assistant.</p><a href="#/business">Open business context ${icon('arrow-right')}</a></div></section>
        <p class="settings-footnote">Appearance is saved in this browser. Your evidence and model training choices stay separate.</p>
      </section>
      <section ${panel('connections')}>
        <div class="settings-pane-heading"><h2>Bring your tools along.</h2><p>Connect only what you need, when you need it.</p></div>
        ${local ? `<section class="panel companion-settings"><div class="connection-heading"><div class="preference-icon">${icon('globe')}</div><div><h3>Chrome companion</h3><p>Save from the page you’re already looking at.</p></div><a href="https://chromewebstore.google.com/detail/proofpage-%E2%80%94-save-page-evi/kiiobhppgpjpccapcejhnagfneopcppk" target="_blank" rel="noopener noreferrer">Install in Chrome ↗</a></div><ol class="connection-steps"><li>Open the Proofpage companion in Chrome.</li><li>Create a code and enter it with this app’s port.</li><li>Preview a page or file, review it, then save.</li></ol><button id="companion-code" class="primary">${icon('plug')}Create connection code</button><div id="companion-result" role="status" aria-live="polite"></div><details class="connection-help"><summary>Connection help & disconnect</summary><p>Keep Proofpage running. Codes expire after five minutes. Reconnect after restarting the app. The companion can import evidence but cannot read your library.</p><button id="companion-revoke" class="secondary">Disconnect browser</button></details></section>` : ''}
        <section class="panel connection-row"><div class="preference-icon">${icon('plug')}</div><div><h3>Your AI assistant</h3><p>Get a setup kit and skill for a compatible local assistant. Search, cite and automate your sources.</p><a href="#/agents">Set up an assistant ${icon('arrow-right')}</a></div></section>
        <section class="panel connection-row"><div class="preference-icon">${icon('file')}</div><div><h3>${local ? 'Google Docs' : 'Business context'}</h3><p>${local ? 'Choose the documents to import as personal context. Your Google password stays with Google.' : 'Review passages before giving context to your assistant.'}</p><a href="#/business">${local ? 'Open Google Docs setup' : 'Review business context'} ${icon('arrow-right')}</a></div></section>
        <a class="settings-inline-link" href="#/sources">Want automatic collection? Set a source schedule ${icon('arrow-right')}</a>
      </section>
      <section ${panel('integrity')}>
        <div class="settings-pane-heading"><h2>A paper trail you can check.</h2><p>Every capture gets a signed receipt. Independent timestamps are optional.</p></div>
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
    </section>
      </section>
      <section ${panel('about')}>
        <div class="settings-pane-heading"><h2>Keep a good thing current.</h2><p>${local ? 'Your app and your library live separately.' : 'About this workspace and its source code.'}</p></div>
        <section class="panel about-panel"><div class="about-brand"><span class="about-seal" aria-hidden="true">p</span><div><h3>${escape(version)}</h3><p>Originals kept. Sources connected.</p></div></div><p>Free and open source. Made by Utsav Das.</p><div class="about-links"><a href="https://github.com/Mehxeo/Proofpage-OpenSource" target="_blank" rel="noopener noreferrer">Source on GitHub ↗</a><a href="https://proofpage.app/docs/" target="_blank" rel="noopener noreferrer">Read the docs ↗</a></div></section>
        ${local ? `<section class="panel update-panel"><h3>App updates</h3><p>Check when you’re ready. This contacts GitHub; no evidence or workspace data is sent.</p><div class="actions"><button id="check-updates" class="primary">${icon('download')}Check for updates</button><a href="https://github.com/Mehxeo/Proofpage-OpenSource/releases/latest" target="_blank" rel="noopener noreferrer">All downloads ↗</a></div><div id="update-result" role="status" aria-live="polite"></div><details><summary>How to update safely</summary><p>Back up your workspace, quit Proofpage, then replace the app with the new download. On Mac, drag the new Proofpage.app into Applications and choose Replace. On Windows or Linux, extract the full download into a new app folder. Open the new app to continue with your existing library.</p><p>Your default library lives in your home folder → Proofpage → data, separate from the app. Keep that folder. Updating currently requires replacing the app; this does not install automatically.</p></details></section>` : ''}
        <a class="settings-inline-link" href="#/start">Revisit getting started ${icon('arrow-right')}</a>
      </section>
      </div>
    </div>`;
  $('appearance-theme').value = selectedTheme;
  $('appearance-theme').onchange = event => {
    const saved = setTheme(event.target.value);
    $('appearance-status').textContent = saved ? 'Theme saved for this browser.' : 'Applied for this visit. Browser storage is unavailable; this preference cannot be saved.';
  };
  $('verify-chain').onclick = () => action(async () => {
    const result = await api('receipts-verify', {});
    $('chain-result').innerHTML = result.ok
      ? `<p class="screening clear">${icon('check')}<span>All ${pluralize(result.receipts, 'receipt')} verified: signatures, hashes, and chain links. Head ${escape((result.head || '').slice(0, 16))}…</span></p>`
      : `<p class="screening">${icon('alert')}<span>${escape(result.problems.join(' '))}</span></p>`;
  }, $('verify-chain'));
  if (!local) return;
  $('check-updates').onclick = () => action(async () => {
    $('update-result').textContent = 'Checking GitHub for the latest stable release…';
    try {
      const result = await api('updates');
      $('update-result').innerHTML = `<p>${result.available ? `Version ${escape(result.latest)} is available. You’re running ${escape(result.current)}.` : `You’re up to date (version ${escape(result.current)}).`}</p>${result.available ? `<a class="button" href="${escape(result.download || result.release_url)}" target="_blank" rel="noopener noreferrer">${result.download ? 'Download update' : 'Choose a download'} ↗</a><p>Quit Proofpage before replacing the app. Keep your data folder.</p>` : ''}`;
    } catch (error) { $('update-result').textContent = error.message; }
  }, $('check-updates'));
  $('attention-notifications').onclick = () => action(async () => { await toggleNotifications(); $('attention-notifications').textContent = notificationsOn() ? 'Turn notifications off' : 'Turn notifications on'; }, $('attention-notifications'));
  $('companion-code').onclick = () => action(async () => {
    const result = await api('companion-code', {});
    $('companion-result').innerHTML = `<div class="pairing-ticket"><span>App port <strong>${escape(String(result.port))}</strong></span><span>Connection code <strong>${escape(result.code)}</strong></span><button type="button" class="secondary small" data-copy="${escape(result.code)}">Copy code</button></div><p>Valid for five minutes. Enter only in the Proofpage companion.</p>`;
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
