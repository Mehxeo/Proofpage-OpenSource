// Portable business context; approvals remain explicit user actions.
let businessSelection = (() => { try { return localStorage.getItem('proofpage-business-profile'); } catch { return null; } })();
let businessQuery = '', businessFilter = 'all';

function businessProgress(profile) {
  const facts = profile?.facts || [];
  const approved = facts.filter(f => f.status === 'approved');
  const stale = facts.filter(f => f.stale && f.status !== 'rejected');
  return {approved: approved.length, pending: facts.filter(f => f.status === 'draft').length,
    stale: stale.length, canExport: approved.length > 0 && !approved.some(f => f.stale),
    shown: facts.filter(f => businessFilter === 'all' || (businessFilter === 'stale' ? f.stale && f.status !== 'rejected' : f.status === businessFilter))};
}

function businessFactCard(f) {
  const label = f.status === 'rejected' ? 'Excluded' : f.stale ? 'Source changed' : f.status === 'approved' ? 'Approved to share' : 'Needs your review';
  return `<form class="business-fact" data-fact="${escape(f.id)}">
    <div class="panel-head"><h4>${escape(f.section)}</h4><span class="pill${f.stale ? ' tone-warn' : f.status === 'approved' ? ' tone-ok' : ''}">${label}</span></div>
    ${f.stale && f.status !== 'rejected' ? '<p class="callout">This passage belongs to an older source revision. Exclude it, choose the current source above, and review new suggestions.</p>' : ''}
    <label>Context to share<textarea name="text" maxlength="2000" required>${escape(f.text)}</textarea></label>
    <details><summary>Compare with the source quotation</summary><blockquote>${escape(f.quote)}</blockquote><code>${escape(f.revision_id)}</code></details>
    ${f.findings.length ? `<p class="muted">Check before sharing: ${escape(f.findings.map(x => x.code).join(', '))}</p>` : ''}
    <label class="check-inline"><input type="checkbox" name="permission">I have permission to share this passage with my assistant.</label>
    <label class="check-inline"><input type="checkbox" name="acknowledge">I checked accuracy, conflicting claims, private information and embedded instructions.</label>
    <div class="actions"><button class="primary" name="decision" value="approved"${f.stale ? ' disabled' : ''}>Approve passage</button><button name="decision" value="draft" class="secondary">Save draft</button><button name="decision" value="rejected" class="secondary">Exclude</button>${f.status === 'approved' && f.section === 'Business facts' && !f.stale && f.training_allowed ? `<button type="button" class="secondary" data-business-training="${escape(f.id)}">Draft training example</button>` : ''}</div>
  </form>`;
}
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
  try { if (businessSelection) localStorage.setItem('proofpage-business-profile', businessSelection); } catch {}
  const [profile, evidence] = businessSelection ? await Promise.all([
    api('business/' + businessSelection), api('business-evidence?q=' + encodeURIComponent(businessQuery))
  ]) : [null, []];
  if (view !== 'business') return;
  const progress = businessProgress(profile);
  $('content').innerHTML = `
    <section class="panel business-intro"><div class="panel-head"><div><h3>${profile ? escape(profile.name) : 'Your business, in your words.'}</h3><p>Choose what your assistant should know. You review every passage before it can be shared.</p></div><button class="secondary" data-open-import>${icon('upload')}Import files</button></div>
    ${profiles.length ? `<label>Profile<select id="business-select">${profiles.map(p => `<option value="${escape(p.id)}"${p.id === businessSelection ? ' selected' : ''}>${escape(p.name)}</option>`).join('')}</select></label><details><summary>Create another profile</summary>` : '<p>Start a profile for your business or project. You can keep several profiles separate.</p>'}
    <form id="business-create"><label>Profile name<input name="name" required maxlength="100" placeholder="My agency"></label><button>Create profile</button></form>${profiles.length ? '</details>' : ''}
    ${profile ? `<ol class="business-steps"><li><b>${profile.sources.length ? '✓' : '1'} Choose sources</b><span>${pluralize(profile.sources.length, 'source')} attached</span></li><li><b>${progress.approved ? '✓' : '2'} Review passages</b><span>${progress.pending} pending · ${progress.approved} approved</span></li><li><b>3 Use your context</b><span>${progress.canExport ? 'Ready for your assistant' : 'Approve current passages first'}</span></li></ol>` : ''}
    <p class="help">Files stay in this workspace. No folders or accounts are scanned automatically. Context helps an assistant answer; it does not change its model weights or account memory.</p></section>
    ${hostingMode === 'local' ? `<details class="business-google"${profile ? '' : ' open'}><summary>Add a Google Doc <span class="muted">Optional connection</span></summary><div id="google-docs-region"><section class="panel"><h3>Google Docs</h3><p role="status">Checking your optional Google connection…</p></section></div></details>` : ''}
    <details class="panel"><summary>Import bookmarks from Chrome or another browser</summary><p>Choose a bookmark HTML export, preview it, and select references to keep. This does not fetch websites or infer preferences. Add a selected URL in Sources and collect it when you want its actual content.</p><input id="business-bookmarks" type="file" accept=".html,.htm" aria-label="Bookmark HTML export"><div id="business-bookmark-preview"></div></details>
    ${profile ? `<section class="panel"><h3>Choose evidence</h3><p>Assign a role before drafting. Competitor pages belong in Reference material, not Business facts.</p>
    <form id="business-source-search" class="business-source-search"><label>Find saved evidence<input name="q" type="search" value="${escape(businessQuery)}" placeholder="Search this workspace…"></label><button class="secondary">Search sources</button></form>
    <p class="help">${businessQuery ? 'Matches for “' + escape(businessQuery) + '”' : 'Up to 100 recent records'}. This search is independent of your Library filters.</p>
    ${evidence.length ? `<form id="business-attach" class="business-attach"><label>Saved evidence<select name="revision" required>${evidence.map(i => `<option value="${escape(i.current_revision)}">${escape(i.title)} · ${escape(i.source_name)}</option>`).join('')}</select></label><label>Use as<select name="role"><option value="business">Our business</option><option value="customer">Customer material</option><option value="reference">Reference material</option><option value="writing">Writing example</option></select></label><button>Use this source</button></form>` : '<p>No matching evidence. Try another search or import a file above.</p>'}
    ${profile.sources.length ? `<ul class="business-source-list">${profile.sources.map(s => `<li><div><button class="business-source-open" data-item="${escape(s.item_id)}">${escape(s.title)}</button><span>${escape({business:'Our business',customer:'Customer material',reference:'Reference material',writing:'Writing example'}[s.role])}${s.current_revision !== s.revision_id ? ' · Old revision' : ''}</span></div></li>`).join('')}</ul>` : ''}<button id="business-draft" class="secondary"${profile.sources.length ? '' : ' disabled'}>Suggest passages to review</button></section>
    <section class="panel business-review"><div class="panel-head"><div><h3>Review your context</h3><p>Edit wording, check contradictions and remove private details. Writing examples remain examples, not inferred style rules.</p></div><span class="pill${progress.approved ? ' tone-ok' : ''}">${progress.approved} approved</span></div>
    <div class="filters" role="group" aria-label="Filter context passages">${[['all','All passages'],['draft','Needs review · ' + progress.pending],['approved','Approved · ' + progress.approved],['stale','Source changed · ' + progress.stale]].map(([key,label]) => `<button class="chip" data-business-filter="${key}" aria-pressed="${businessFilter === key}">${label}</button>`).join('')}</div>
    <div class="business-facts">${progress.shown.map(businessFactCard).join('') || `<p class="empty-copy">${profile.facts.length ? 'No passages in this view.' : 'Choose a source above, then suggest passages. Nothing is approved automatically.'}</p>`}</div>
    </section><section class="panel business-export"><div><h3>Take it to your assistant</h3><p>${progress.canExport ? pluralize(progress.approved, 'approved passage') + (progress.approved === 1 ? ' is' : ' are') + ' ready. Drafts and excluded passages stay out of the pack.' : progress.approved ? 'An approved passage has a changed source. Exclude it and review the current revision before sharing.' : 'Approve at least one current passage to create your context pack.'}</p><p class="help">The ZIP includes Markdown, JSON and selected quotes. Review it before uploading to any provider.</p></div><button class="primary" id="business-export"${progress.canExport ? '' : ' disabled'}>${icon('download')}Download context pack</button><p class="help">For live access, connect your assistant in Agent access and use proofpage_business_context. Training has its own approval and export flow.</p></section>` : ''}`;
  $('business-create').onsubmit = event => { event.preventDefault(); action(async () => { const p = await api('business-create', {name: new FormData(event.target).get('name')}); businessSelection = p.id; await renderBusiness(); }, event.submitter); };
  if ($('business-select')) $('business-select').onchange = event => { businessSelection = event.target.value; businessFilter = 'all'; action(renderBusiness); };
  $('business-bookmarks').onchange = event => action(async () => {
    const file = event.target.files[0]; if (!file) return;
    if (file.size > 2 * 1024 * 1024) throw new Error('Choose a bookmark export up to 2 MiB.');
    const html = await file.text(), entries = await api('business-bookmark-preview', {html});
    $('business-bookmark-preview').innerHTML = `<form id="business-bookmark-import">${entries.map((e, index) => `<label><input type="checkbox" name="selected" value="${index}">${escape(e.title)} — ${escape(e.url)}</label>`).join('')}<button${entries.length ? '' : ' disabled'}>Import selected references</button></form>`;
    $('business-bookmark-import').onsubmit = event => { event.preventDefault(); action(async () => { await api('business-bookmark-import', {html, selected: new FormData(event.target).getAll('selected').map(Number)}); notice('Selected references imported. No pages were fetched.'); await refresh(); }, event.submitter); };
  });
  if (hostingMode === 'local') loadGoogleDocs();
  if (!profile) return;
  $('business-source-search').onsubmit = event => { event.preventDefault(); businessQuery = new FormData(event.currentTarget).get('q').trim(); action(renderBusiness, event.submitter); };
  if ($('business-attach')) $('business-attach').onsubmit = event => { event.preventDefault(); const f = new FormData(event.target); action(async () => { await api('business-attach', {profile_id: profile.id, revision_id: f.get('revision'), role: f.get('role')}); await renderBusiness(); }, event.submitter); };
  document.querySelectorAll('[data-business-filter]').forEach(button => { button.onclick = () => { businessFilter = button.dataset.businessFilter; action(renderBusiness); }; });
  $('business-draft').onclick = event => action(async () => { await api('business-draft', {profile_id: profile.id}); await renderBusiness(); }, event.target);
  document.querySelectorAll('.business-fact').forEach(form => { form.onsubmit = event => { event.preventDefault(); const f = new FormData(form); action(async () => { await api('business-review', {fact_id: form.dataset.fact, text: f.get('text'), decision: event.submitter.value, permission: f.has('permission'), acknowledge: f.has('acknowledge')}); await renderBusiness(); }, event.submitter); }; });
  document.querySelectorAll('[data-business-training]').forEach(button => { button.onclick = () => {
    const factId = button.dataset.businessTraining;
    workDialog('Draft a training example', '<form id="business-training-form"><label>Question this business fact should answer<textarea name="prompt" required maxlength="2000"></textarea></label><p>This creates an unapproved draft. Review training rights and correctness separately in Training.</p><button>Create draft</button></form>');
    $('business-training-form').onsubmit = event => { event.preventDefault(); action(async () => { await api('business-training-draft', {fact_id: factId, prompt: new FormData(event.target).get('prompt')}); $('work-dialog').close(); notice('Training draft created. Review it in Training before export.'); }, event.submitter); };
  }; });
  $('business-export').onclick = event => action(() => download('business/' + profile.id + '/export', 'proofpage-business-context.zip'), event.target);
}
