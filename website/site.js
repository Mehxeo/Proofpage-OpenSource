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

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const art = document.querySelector('.paper-field pre');
const lines = art.textContent.split('\n'); art.textContent = '';
lines.forEach((line, i) => { const row = document.createElement('span'); row.textContent = line || ' '; row.style.setProperty('--row', i); art.append(row); });
let motionPaused = false, captureFrame = 0;
const stages = ['01 / Capture the page', '02 / Preserve the original', '03 / Sign the receipt', '04 / Check the quoted words'];
$('motion-toggle').addEventListener('click', () => { motionPaused = !motionPaused; document.body.classList.toggle('motion-paused', motionPaused); $('motion-toggle').textContent = motionPaused ? 'Play animation' : 'Pause animation'; $('motion-toggle').setAttribute('aria-pressed', String(motionPaused)); });
setInterval(() => { if (motionPaused || reducedMotion.matches || document.hidden) return; captureFrame = (captureFrame + 1) % stages.length; $('capture-step').textContent = stages[captureFrame]; }, 2400);
if (!reducedMotion.matches && 'IntersectionObserver' in window) { const observer = new IntersectionObserver(entries => { entries.forEach(entry => { if(entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }); }, {threshold:.08}); document.querySelectorAll('.section-heading,.app-shot,.feature-grid article,.maker').forEach(el => { el.classList.add('reveal-ready'); observer.observe(el); }); }
const screens = { library: ['/images/library.png', 'Proofpage library showing captured sources, review controls, and the evidence workspace', 'Your library: captured pages, immutable revisions, and evidence you can inspect.'], claims: ['/images/claim-check.png', 'Proofpage Claim Check showing a checked answer and citation matching results', 'Claim Check: trace quoted wording back to captured evidence.'] };
document.querySelectorAll('[data-screen]').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('[data-screen]').forEach(b => b.setAttribute('aria-pressed', String(b===button))); const [src,alt,caption] = screens[button.dataset.screen]; $('app-screenshot').src=src; $('app-screenshot').alt=alt; $('screenshot-caption').textContent=caption; }));
