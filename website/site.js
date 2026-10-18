const $ = id => document.getElementById(id);
const theme = $('theme');
function setTheme(light) { document.body.classList.toggle('light', light); theme.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme'); }
try { setTheme(localStorage.getItem('proofpage-site-theme') === 'light'); } catch {}
theme.addEventListener('click', () => { const light = !document.body.classList.contains('light'); setTheme(light); try { localStorage.setItem('proofpage-site-theme', light ? 'light' : 'dark'); } catch {} });
const examples = {
 exact: ['“The archive is available for research and education.”', '✓ Exact wording', 'The archive is available for research and education.', 'The wording matches the saved passage. You can inspect the original capture and its signed receipt.'],
 changed: ['“The archive is available for commercial use.”', '↔ Changed wording', 'The archive is available for research and education.', 'The answer changed the permitted purpose. Review the actual passage before relying on the claim.'],
 missing: ['“The archive guarantees that every record is accurate.”', '? Not found', 'The archive is available for research and education.', 'This claim does not appear in the captured passage. A confident answer is not a substitute for a source.']
};
document.querySelectorAll('[data-example]').forEach(b => b.addEventListener('click', () => { document.querySelectorAll('[data-example]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); const [quote,status,evidence,detail] = examples[b.dataset.example]; $('demo-quote').textContent=quote; $('demo-status').textContent=status; $('demo-status').classList.toggle('warning',b.dataset.example!=='exact'); $('demo-evidence').textContent=evidence; $('demo-detail').textContent=detail; }));
function platform(name) { document.querySelectorAll('[data-platform]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.platform===name))); document.querySelectorAll('.platform-panel').forEach(p => p.hidden = p.id !== 'platform-'+name); }
document.querySelectorAll('[data-platform]').forEach(b => b.addEventListener('click', () => platform(b.dataset.platform)));
if (/Win/.test(navigator.platform)) platform('windows'); else if (/Linux/.test(navigator.platform)) platform('linux');
$('copy-command').addEventListener('click',async () => { try { await navigator.clipboard.writeText($('install-command').textContent); $('copy-status').textContent='Commands copied.'; } catch { $('copy-status').textContent='Select and copy the commands above.'; } });
