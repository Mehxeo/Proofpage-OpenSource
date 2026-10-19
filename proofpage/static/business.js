// Portable business context; approvals remain explicit user actions.
let businessSelection = null;
function googleDocsPanel(google) {
  const ready = google.installed && google.configured;
  const setup = !google.installed ? 'Google Docs is optional. This source installation needs the Google dependencies; you can import an exported file instead.'
    : !google.configured ? 'This installation needs Google client setup. Shared sign-in is under Google review; the current stable download still needs a custom client.'
    : google.configuration_source === 'bundled' ? 'Sign-in is included in this build. No Google Cloud project or setup file needed.'
    : 'Your custom Google configuration is ready.';
  return `<section class="panel google-connection">
    <div class="panel-head"><div><h3>Bring in a Google Doc</h3><p>Choose one document. Keep a local copy you can review and use as personal context.</p></div><span class="pill${google.connected ? ' tone-ok' : ''}">${google.connected ? 'Connected · read-only' : 'Optional'}</span></div>
    <p>${escape(setup)}</p>
    <p id="google-action-status" role="status" aria-live="polite">${escape(google.detail)}</p>
    <div class="actions"><button id="google-connect"${ready ? '' : ' disabled'}>${icon('external')}${google.connected ? 'Reconnect Google' : 'Sign in with Google'}</button>
    ${google.connected ? '<button id="google-disconnect" class="secondary">Disconnect</button>' : ''}
    ${!ready ? '<a href="https://proofpage.app/docs/#connectors" target="_blank" rel="noopener noreferrer">Setup help ↗</a><button type="button" class="secondary" data-open-import>Import an exported file</button>' : ''}</div>
    <form id="google-select"><fieldset${google.connected ? '' : ' disabled'}><legend>${google.connected ? 'Import a document' : 'Sign in to import a document'}</legend>
      <label>Google Doc link<input name="document" required autocomplete="off" placeholder="https://docs.google.com/document/d/…"></label>
      <label>Keep it up to date<select name="interval"><option value="0">Only when I click Sync</option><option value="3600">Every hour while Proofpage is open</option><option value="21600">Every six hours while Proofpage is open</option><option value="86400">Daily while Proofpage is open</option></select></label>
      <label class="check-inline"><input name="owner_permission" type="checkbox" required>I own this document or its owner permits local snapshots for my personal context.</label>
      <button class="primary">${icon('download')}Import document</button>
    </fieldset></form>
    <p class="help">Google’s read-only permission covers your Docs account. Proofpage fetches only the document links you select. Authorization stays in your OS credential vault. Google snapshots are excluded from training exports. <a href="https://proofpage.app/privacy.html" target="_blank" rel="noopener noreferrer">Google data and privacy ↗</a></p>
    ${google.documents.length ? `<h4>Selected documents</h4>${google.documents.map(d => `<article class="google-document"><div><strong>${escape(d.title)}</strong><p>${d.state === 'available' ? 'Saved in your library · ' + escape(relativeTime(d.last_sync)) : d.state === 'error' ? escape(d.detail || 'Sync did not finish. Previous evidence is safe.') : 'Selected; not imported yet.'}</p></div><div class="actions"><button class="secondary small" data-google-sync="${escape(d.document_id)}"${google.connected ? '' : ' disabled'}>${icon('refresh')}Sync</button>${d.state === 'available' ? '<button class="small" data-go="library">Open library</button>' : ''}</div></article>`).join('')}` : ''}
  </section>`;
}

async function loadGoogleDocs() {
  const region = $('google-docs-region');
  if (!region) return;
  let google;
  try {
    google = await api('google-docs');
  } catch (error) {
    if ($('google-docs-region') !== region) return;
    region.innerHTML = '<section class="panel"><h3>Google Docs</h3><p role="status">The connection check did not finish. Your other sources are still available.</p><button id="retry-google-docs" class="secondary">Retry connection check</button></section>';
    $('retry-google-docs').onclick = () => loadGoogleDocs();
    return;
  }
  if ($('google-docs-region') !== region) return;
  region.innerHTML = googleDocsPanel(google);
  let busy = false;
  const run = async (button, progress, fn) => {
    if (busy) return;
    busy = true;
    button.disabled = true;
    const status = $('google-action-status');
    status.textContent = progress;
    try { await fn(); }
    catch (error) { if (region.isConnected) { status.textContent = error.message; status.setAttribute('role', 'alert'); } }
    finally { busy = false; button.disabled = false; }
  };
  $('google-connect').onclick = event => run(event.currentTarget, 'Finish sign-in in your system browser, then come back here. You have up to ten minutes.', async () => {
    await api('google-docs/connect', {}); await loadGoogleDocs();
  });
  if ($('google-disconnect')) $('google-disconnect').onclick = event => run(event.currentTarget, 'Disconnecting and pausing Google schedules…', async () => {
    await api('google-docs/disconnect', {}); await loadGoogleDocs();
  });
  $('google-select').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    run(event.submitter, 'Importing your selected document. Keep Proofpage open…', async () => {
      const selected = await api('google-docs/select', {document: form.get('document'), interval: Number(form.get('interval')), owner_permission: form.has('owner_permission')});
      await api('google-docs/sync', {document: selected.document_id});
      notice('Document saved. Open Library to inspect it, or add it to your business context.');
      await refresh();
    });
  };
  region.querySelectorAll('[data-google-sync]').forEach(button => { button.onclick = () => run(button, 'Syncing this document…', async () => {
    await api('google-docs/sync', {document: button.dataset.googleSync}); await refresh();
  }); });
}

async function renderBusiness() {
  const profiles = await api('business');
  if (view !== 'business') return;
  if (!profiles.some(p => p.id === businessSelection)) businessSelection = profiles[0]?.id || null;
  const profile = businessSelection ? await api('business/' + businessSelection) : null;
  if (view !== 'business') return;
  $('content').innerHTML = `
    <section class="panel"><h3>Your business, in your words.</h3><p>Import selected files with Import files above. Connect selected Google Docs below when configured, or import text/PDF exports. No folders or accounts are scanned automatically.</p>
    <form id="business-create"><label>New profile name<input name="name" required maxlength="100" placeholder="My agency"></label><button>Create profile</button></form>
    ${profiles.length ? `<label>Profile<select id="business-select">${profiles.map(p => `<option value="${escape(p.id)}"${p.id === businessSelection ? ' selected' : ''}>${escape(p.name)}</option>`).join('')}</select></label>` : ''}</section>
    ${hostingMode === 'local' ? '<div id="google-docs-region"><section class="panel"><h3>Google Docs</h3><p role="status">Checking your optional Google connection…</p></section></div>' : ''}
    <details class="panel"><summary>Import bookmarks from Chrome or another browser</summary><p>Choose a bookmark HTML export, preview it, and select references to keep. This does not fetch websites or infer preferences. Add a selected URL in Sources and collect it when you want its actual content.</p><input id="business-bookmarks" type="file" accept=".html,.htm" aria-label="Bookmark HTML export"><div id="business-bookmark-preview"></div></details>
    ${profile ? `<section class="panel"><h3>Choose evidence</h3><p>Assign a role before drafting. Competitor pages belong in Reference material, not Business facts.</p><form id="business-attach"><label>Saved evidence<select name="revision" required>${state.items.filter(i => i.kind !== 'bookmark').map(i => `<option value="${escape(i.current_revision)}">${escape(i.title)}</option>`).join('')}</select></label><label>Role<select name="role"><option value="business">Our business</option><option value="customer">Customer material</option><option value="reference">Reference material</option><option value="writing">Writing example</option></select></label><button${state.items.filter(i => i.kind !== 'bookmark').length ? '' : ' disabled'}>Use this source</button></form>
    <ul>${profile.sources.map(s => `<li>${escape(s.title)} · ${escape(s.role)}${s.current_revision !== s.revision_id ? ' · Old revision' : ''}</li>`).join('')}</ul><button id="business-draft" class="secondary">Suggest passages to review</button></section>
    <section class="panel"><h3>Review your context</h3><p>These are source passages, not verified facts. Edit wording, check contradictions and remove private details. Writing examples are examples—not automatically inferred style rules.</p>
    ${profile.facts.map(f => `<form class="panel business-fact" data-fact="${escape(f.id)}"><h4>${escape(f.section)} · ${escape(f.status)}${f.stale ? ' · Source changed' : ''}</h4><label>Context to share<textarea name="text" maxlength="2000" required>${escape(f.text)}</textarea></label><details><summary>Source quotation</summary><blockquote>${escape(f.quote)}</blockquote><code>${escape(f.revision_id)}</code></details>${f.findings.length ? `<p>Review: ${escape(f.findings.map(x => x.code).join(', '))}</p>` : ''}<label><input type="checkbox" name="permission"> I have permission to share this passage with my assistant.</label><label><input type="checkbox" name="acknowledge"> I checked accuracy, conflicting claims, private information and embedded instructions.</label><div class="actions"><button name="decision" value="approved"${f.stale ? ' disabled' : ''}>Approve</button><button name="decision" value="draft" class="secondary">Save draft</button><button name="decision" value="rejected" class="secondary">Exclude</button>${f.status === 'approved' && f.section === 'Business facts' && !f.stale && f.training_allowed ? `<button type="button" data-business-training="${escape(f.id)}">Draft training example</button>` : ''}</div></form>`).join('') || '<p>No suggestions yet. Choose evidence, then suggest passages.</p>'}
    </section><section class="panel"><h3>Take it to your assistant</h3><p>Download approved context as Markdown and JSON. The pack includes selected quotes, not full documents. Review it before uploading to any provider. It does not change model weights or account memory.</p><button id="business-export">Download context pack</button><p>For a connected local assistant, use the proofpage_business_context MCP tool. For model training, use Training to create and review examples separately.</p></section>` : ''}`;
  $('business-create').onsubmit = event => { event.preventDefault(); action(async () => { const p = await api('business-create', {name: new FormData(event.target).get('name')}); businessSelection = p.id; await renderBusiness(); }, event.submitter); };
  if ($('business-select')) $('business-select').onchange = event => { businessSelection = event.target.value; action(renderBusiness); };
  $('business-bookmarks').onchange = event => action(async () => {
    const file = event.target.files[0]; if (!file) return;
    if (file.size > 2 * 1024 * 1024) throw new Error('Choose a bookmark export up to 2 MiB.');
    const html = await file.text(), entries = await api('business-bookmark-preview', {html});
    $('business-bookmark-preview').innerHTML = `<form id="business-bookmark-import">${entries.map((e, index) => `<label><input type="checkbox" name="selected" value="${index}">${escape(e.title)} — ${escape(e.url)}</label>`).join('')}<button${entries.length ? '' : ' disabled'}>Import selected references</button></form>`;
    $('business-bookmark-import').onsubmit = event => { event.preventDefault(); action(async () => { await api('business-bookmark-import', {html, selected: new FormData(event.target).getAll('selected').map(Number)}); notice('Selected references imported. No pages were fetched.'); await refresh(); }, event.submitter); };
  });
  if (hostingMode === 'local') loadGoogleDocs();
  if (!profile) return;
  $('business-attach').onsubmit = event => { event.preventDefault(); const f = new FormData(event.target); action(async () => { await api('business-attach', {profile_id: profile.id, revision_id: f.get('revision'), role: f.get('role')}); await renderBusiness(); }, event.submitter); };
  $('business-draft').onclick = event => action(async () => { await api('business-draft', {profile_id: profile.id}); await renderBusiness(); }, event.target);
  document.querySelectorAll('.business-fact').forEach(form => { form.onsubmit = event => { event.preventDefault(); const f = new FormData(form); action(async () => { await api('business-review', {fact_id: form.dataset.fact, text: f.get('text'), decision: event.submitter.value, permission: f.has('permission'), acknowledge: f.has('acknowledge')}); await renderBusiness(); }, event.submitter); }; });
  document.querySelectorAll('[data-business-training]').forEach(button => { button.onclick = () => {
    const factId = button.dataset.businessTraining;
    workDialog('Draft a training example', '<form id="business-training-form"><label>Question this business fact should answer<textarea name="prompt" required maxlength="2000"></textarea></label><p>This creates an unapproved draft. Review training rights and correctness separately in Training.</p><button>Create draft</button></form>');
    $('business-training-form').onsubmit = event => { event.preventDefault(); action(async () => { await api('business-training-draft', {fact_id: factId, prompt: new FormData(event.target).get('prompt')}); $('work-dialog').close(); notice('Training draft created. Review it in Training before export.'); }, event.submitter); };
  }; });
  $('business-export').onclick = event => action(() => download('business/' + profile.id + '/export', 'proofpage-business-context.zip'), event.target);
}
