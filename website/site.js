const $ = id => document.getElementById(id);
const theme = $('theme');
function setTheme(light) { document.body.classList.toggle('light', light); theme.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme'); }
try { setTheme(localStorage.getItem('proofpage-site-theme') === 'light'); } catch {}
theme.onclick = () => { const light = !document.body.classList.contains('light'); setTheme(light); try { localStorage.setItem('proofpage-site-theme', light ? 'light' : 'dark'); } catch {} };
function platform(name) { document.querySelectorAll('[data-platform]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.platform===name))); document.querySelectorAll('.platform-panel').forEach(p => p.hidden = p.id !== 'platform-'+name); }
document.querySelectorAll('[data-platform]').forEach(b => b.onclick = () => platform(b.dataset.platform));
if (/Win/.test(navigator.platform)) platform('windows'); else if (/Linux/.test(navigator.platform)) platform('linux');
$('copy-command').onclick=async()=>{try{await navigator.clipboard.writeText($('install-command').textContent);$('copy-status').textContent='Commands copied.';}catch{$('copy-status').textContent='Select and copy the commands above.';}};
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const transcript = '$ collect public-source\n✓ original preserved\n✓ revision hash recorded\n\n$ retrieve cited-context\n→ passage + source + receipt\n\n$ draft training-example\n→ ready for your review';
let typed=0, paused=motion.matches, hold=0;
function updateMotion(){ $('motion-toggle').textContent=paused?'Play':'Pause'; $('motion-toggle').setAttribute('aria-pressed',String(paused)); }
$('motion-toggle').onclick=()=>{paused=!paused;updateMotion();};
if(motion.matches){$('typed-workflow').textContent=transcript;typed=transcript.length;}updateMotion();
motion.addEventListener('change',e=>{paused=e.matches;if(paused){$('typed-workflow').textContent=transcript;$('product-film').pause();}updateMotion();});
setInterval(()=>{if(paused||document.hidden)return;if(typed<transcript.length){$('typed-workflow').textContent=transcript.slice(0,++typed);}else if(++hold>90){typed=0;hold=0;}},55);
// Video is user-initiated: no autoplay, no surprise downloads or motion.
$('product-film').addEventListener('error',()=>{document.querySelector('.film-bottom p').textContent='Video unavailable. Read the walkthrough below or download the MP4.';});

const film=$('product-film');
$('play-tour').onclick=async()=>{if(film.paused){try{await film.play();}catch{$('play-tour').textContent='Use the video controls to play';}}else film.pause();};
film.addEventListener('play',()=>{$('play-tour').textContent='Pause tour Ⅱ';});
film.addEventListener('pause',()=>{$('play-tour').textContent='Play the 18-second tour ▷';});
film.addEventListener('ended',()=>{$('play-tour').textContent='Replay tour ↻';});
