// Exercise actual theme code with browser/storage stand-ins; no dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('proofpage/static/ui.js', 'utf8').split('// ---------- Theme ----------')[1].split('// ---------- Command palette')[0];
function browser(saved, blocked = false) {
  const values = new Map(saved ? [['proofpage-theme', saved]] : []);
  const events = {};
  const media = {matches: false, addEventListener: (_, fn) => events.system = fn};
  const button = {setAttribute() {}};
  const select = {};
  const context = vm.createContext({document: {documentElement: {dataset: {}}},
    matchMedia: () => media, icon: x => x, notice() {},
    $: id => id === 'theme-toggle' ? button : select,
    window: {addEventListener: (name, fn) => events[name] = fn},
    localStorage: {getItem: key => {if (blocked) throw Error(); return values.get(key);},
      setItem: (key, value) => {if (blocked) throw Error(); values.set(key, value);}}});
  vm.runInContext(source, context);
  return {context, values, media, events, select, run: code => vm.runInContext(code, context)};
}
const b = browser('invalid');
assert.equal(b.run('currentTheme()'), 'light');
b.media.matches = true; b.events.system();
assert.equal(b.run('currentTheme()'), 'dark');
b.run("setTheme('light')"); b.events.system();
assert.equal(b.run('currentTheme()'), 'light');
assert.equal(browser(b.values.get('proofpage-theme')).run('currentTheme()'), 'light');
b.run("setTheme('system')");
assert.equal(b.run('currentTheme()'), 'dark');
b.values.set('proofpage-theme', 'light'); b.events.storage({key: 'proofpage-theme'});
assert.equal(b.select.value, 'light');
b.run('toggleTheme()'); assert.equal(b.select.value, 'dark');
const blocked = browser(null, true);
assert.equal(blocked.run("setTheme('dark')"), false);
assert.equal(blocked.run('currentTheme()'), 'dark');
console.log('Preferences: persistence, system changes, cross-tab sync, invalid values and unavailable storage passed.');
