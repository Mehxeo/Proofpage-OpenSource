// Exercise the actual Google onboarding handlers without network or browser dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('proofpage/static/business.js', 'utf8');
const turn = () => new Promise(resolve => setImmediate(resolve));
const connected = {installed: true, configured: true, connected: true, configuration_source: 'bundled', detail: '', documents: []};

function screen(respond) {
  const elements = new Map();
  const calls = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {innerHTML: '', textContent: '', disabled: false,
      isConnected: true, setAttribute() {}, querySelectorAll: () => []});
    return elements.get(id);
  };
  let refreshes = 0;
  const context = vm.createContext({
    $: element, view: 'business', hostingMode: 'local', state: {items: []},
    escape: x => String(x ?? ''), icon: () => '', relativeTime: () => 'just now',
    notice() {}, refresh: async () => { refreshes++; },
    FormData: class { constructor(value) { this.value = value; } get(key) { return this.value[key]; } has(key) { return this.value[key] === true; } },
    api: async (path, data) => { calls.push({path, data}); return respond(path, data); },
  });
  vm.runInContext(source, context);
  return {elements, calls, element, run: code => vm.runInContext(code, context), refreshes: () => refreshes};
}

(async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const success = screen(path => path === 'google-docs' ? connected : path === 'google-docs/select' ? {document_id: 'selected-demo'} : pending);
  await success.run('loadGoogleDocs()');
  const button = {disabled: false};
  const event = {preventDefault() {}, submitter: button, currentTarget: {
    document: 'https://docs.google.com/document/d/selected-demo/edit', interval: '3600', owner_permission: true,
  }};
  success.element('google-select').onsubmit(event);
  await turn();
  assert.equal(button.disabled, true);
  // A second click must not create another selection or sync while the first runs.
  success.element('google-select').onsubmit(event);
  await turn();
  assert.deepEqual(success.calls.map(x => x.path), ['google-docs', 'google-docs/select', 'google-docs/sync']);
  assert.equal(success.calls[1].data.owner_permission, true);
  assert.equal(success.calls[1].data.interval, 3600);
  assert.equal(success.calls[2].data.document, 'selected-demo');
  finish({revision_id: 'saved-revision'});
  await turn();
  assert.equal(button.disabled, false);
  assert.equal(success.refreshes(), 1);

  const failure = screen(path => {
    if (path === 'google-docs') return connected;
    if (path === 'google-docs/select') return {document_id: 'selected-demo'};
    throw Error('Reconnect Google, then retry this document. Existing evidence was retained.');
  });
  await failure.run('loadGoogleDocs()');
  const originalMarkup = failure.element('google-docs-region').innerHTML;
  failure.element('google-select').onsubmit(event);
  await turn();
  assert.match(failure.element('google-action-status').textContent, /Reconnect Google/);
  assert.equal(failure.refreshes(), 0);
  assert.equal(failure.element('google-docs-region').innerHTML, originalMarkup);
  assert.equal(button.disabled, false);

  let resolveStatus;
  const navigation = screen(() => new Promise(resolve => { resolveStatus = resolve; }));
  const loading = navigation.run('loadGoogleDocs()');
  const currentScreen = {innerHTML: 'A different screen'};
  navigation.elements.set('google-docs-region', currentScreen);
  resolveStatus(connected);
  await loading;
  assert.equal(currentScreen.innerHTML, 'A different screen');

  const offline = screen(() => { throw Error('Offline'); });
  await offline.run('loadGoogleDocs()');
  assert.equal(typeof offline.element('retry-google-docs').onclick, 'function');
  assert.match(offline.element('google-docs-region').innerHTML, /other sources are still available/);
  console.log('Google onboarding: one-action import, duplicate prevention, recoverable errors, navigation and retry passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
