'use strict';

const $ = id => document.getElementById(id);
const motion = matchMedia('(prefers-reduced-motion: reduce)');
let paused = motion.matches;
try { paused ||= localStorage.getItem('proofpage-site-motion') === 'paused'; } catch {}
const forest = $('note-forest');
let forestVisible = true;

function syncForest() {
  if (!forest) return;
  forest.classList.toggle('is-dormant', paused || document.hidden || !forestVisible);
  if (paused || document.hidden || !forestVisible) {
    forest.style.removeProperty('--forest-x');
    forest.style.removeProperty('--forest-y');
  }
}

function setTheme(light) {
  document.body.classList.toggle('light', light);
  $('theme').setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
}
try { setTheme(localStorage.getItem('proofpage-site-theme') === 'light'); } catch {}
$('theme').addEventListener('click', () => {
  const light = !document.body.classList.contains('light');
  setTheme(light);
  try { localStorage.setItem('proofpage-site-theme', light ? 'light' : 'dark'); } catch {}
});

function platform(name) {
  document.querySelectorAll('[data-platform]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.platform === name)));
  document.querySelectorAll('.platform-panel').forEach(panel => { panel.hidden = panel.id !== `platform-${name}`; });
}
document.querySelectorAll('[data-platform]').forEach(button => button.addEventListener('click', () => platform(button.dataset.platform)));
if (/Win/.test(navigator.platform)) platform('windows');
else if (/Linux/.test(navigator.platform)) platform('linux');
$('copy-command').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('install-command').textContent);
    $('copy-status').textContent = 'Commands copied.';
  } catch { $('copy-status').textContent = 'Select and copy the commands above.'; }
});

// These are explicitly illustrative outputs, never network calls or live claims.
const scenes = {
  capture: {
    lines: [
      ['command', '$ proofpage collect https://example.com'],
      ['output', ''],
      ['output', '  original body         preserved'],
      ['output', '  publisher signals     recorded'],
      ['success', '  capture receipt       signed'],
      ['output', ''],
      ['output', '  source → revision → receipt'],
      ['output', ''],
      ['success', '  ready for your review']
    ],
    transcript: 'Capture: collect a public page, preserve its original, and record a signed capture receipt for review.',
    number: '001', title: 'SOURCE CAPTURED', stamp: '✓', hash: 'original → hash → receipt',
    guide: '/docs/#start', link: 'How collection works ↗'
  },
  check: {
    lines: [
      ['command', '$ proofpage check-answer answer.md'],
      ['output', ''],
      ['output', '  “The price is $20.”'],
      ['success', '  ✓ matched in saved revision'],
      ['output', ''],
      ['output', '  “The price is $10.”'],
      ['warning', '  ! wording not found in source'],
      ['output', ''],
      ['output', '  wording checked ≠ truth proven']
    ],
    transcript: 'Check: compare cited quotes with saved evidence. The example flags a changed price. A wording match does not prove truth.',
    number: '002', title: 'WORDS CHECKED', stamp: '≠', hash: 'quote → source → difference',
    guide: '/docs/#verify', link: 'How quote checking works ↗'
  },
  replay: {
    lines: [
      ['command', '$ proofpage evidence replay inputs.json'],
      ['output', ''],
      ['success', '  recorded input        restored'],
      ['output', '  source revision       pinned'],
      ['output', '  network requests      0'],
      ['output', ''],
      ['output', '  same passage. same source.'],
      ['output', ''],
      ['success', '  inspect the input behind the answer']
    ],
    transcript: 'Replay: restore the exact recorded evidence offline, with zero network requests. Model outputs may still differ.',
    number: '003', title: 'INPUTS REPLAYED', stamp: '↻', hash: 'record → pin → replay',
    guide: '/docs/#developers', link: 'Build a reproducible workflow ↗'
  }
};
let selectedScene = 'capture';
let characters = 0;
let typeTimer = 0;
let terminalVisible = true;
const terminal = $('typed-workflow');

function renderTerminal(complete = false) {
  const scene = scenes[selectedScene];
  let remaining = complete ? Infinity : characters;
  const nodes = [];
  for (let index = 0; index < scene.lines.length; index++) {
    const [kind, line] = scene.lines[index];
    if (remaining <= 0) break;
    const span = document.createElement('span');
    span.className = kind;
    span.textContent = line.slice(0, remaining);
    nodes.push(span);
    remaining -= line.length;
    if (index < scene.lines.length - 1 && remaining > 0) {
      nodes.push(document.createTextNode('\n'));
      remaining--;
    }
  }
  if (!complete) {
    const cursor = document.createElement('span');
    cursor.className = 'typing-cursor';
    nodes.push(cursor);
  }
  terminal.replaceChildren(...nodes);
}

function typeNext() {
  clearTimeout(typeTimer);
  if (paused || document.hidden || !terminalVisible) return;
  const length = scenes[selectedScene].lines.reduce((sum, [, line]) => sum + line.length + 1, -1);
  if (characters >= length) { renderTerminal(true); return; }
  const commandLength = scenes[selectedScene].lines[0][1].length;
  // Commands are typed; output arrives a few characters at a time.
  characters = Math.min(length, characters + (characters < commandLength ? 1 : 3));
  renderTerminal();
  typeTimer = setTimeout(typeNext, characters < commandLength ? 36 + (characters % 4) * 13 : 28);
}

function chooseScene(name) {
  if (!scenes[name]) return;
  clearTimeout(typeTimer);
  selectedScene = name;
  characters = 0;
  document.querySelectorAll('[data-scene]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scene === name)));
  const scene = scenes[name];
  $('workflow-transcript').textContent = scene.transcript;
  $('workflow-guide').href = scene.guide;
  $('workflow-guide').textContent = scene.link;
  $('receipt-number').textContent = scene.number;
  $('receipt-title').textContent = scene.title;
  $('receipt-stamp').textContent = scene.stamp;
  $('receipt-hash').textContent = scene.hash;
  renderTerminal(paused);
  typeNext();
  if (!paused && !motion.matches && typeof $('receipt-stamp').animate === 'function') {
    $('receipt-stamp').animate([{ transform: 'scale(.75) rotate(-18deg)', opacity: .2 }, { transform: 'scale(1) rotate(0deg)', opacity: 1 }], { duration: 420, easing: 'cubic-bezier(.2,.7,.2,1)' });
  }
}
document.querySelectorAll('[data-scene]').forEach(button => button.addEventListener('click', () => chooseScene(button.dataset.scene)));
$('replay-terminal').addEventListener('click', () => chooseScene(selectedScene));

// A small native Canvas field: no WebGL dependency, trackers, or external assets.
const canvas = $('evidence-rain');
const context = canvas.getContext('2d');
let canvasWidth = 0, canvasHeight = 0, rainFrame = 0, lastPaint = 0;
let drops = [];
const alphabet = '.:+01/<>[]{}#';
let fieldPointer = null;
canvas.addEventListener('pointermove', event => {
  const rect = canvas.getBoundingClientRect();
  fieldPointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
});
canvas.addEventListener('pointerleave', () => { fieldPointer = null; });

function sizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  canvasWidth = rect.width;
  canvasHeight = rect.height;
  const ratio = Math.min(devicePixelRatio || 1, 2);
  canvas.width = Math.round(canvasWidth * ratio);
  canvas.height = Math.round(canvasHeight * ratio);
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  drops = Array.from({ length: Math.ceil(canvasWidth / 19) }, (_, i) => ({
    x: i * 19 + 7, y: (i * 83) % (canvasHeight + 140) - 90,
    speed: 12 + (i * 7) % 19, offset: i * 3
  }));
  paintRain(0);
}

function paintRain(delta) {
  if (!context || !canvasWidth) return;
  context.clearRect(0, 0, canvasWidth, canvasHeight);
  context.font = '10px "Proof Mono", monospace';
  context.textAlign = 'center';
  drops.forEach(drop => {
    drop.y += delta * drop.speed;
    if (drop.y > canvasHeight + 105) { drop.y = -30; drop.offset++; }
    for (let tail = 0; tail < 7; tail++) {
      const y = drop.y - tail * 17;
      if (y < 0 || y > canvasHeight) continue;
      const distance = fieldPointer ? Math.hypot(drop.x - fieldPointer.x, y - fieldPointer.y) : 200;
      const bend = distance < 100 ? (1 - distance / 100) * (drop.x < fieldPointer.x ? -24 : 24) : 0;
      context.fillStyle = `rgba(177, 207, 132, ${(.42 - tail * .052).toFixed(3)})`;
      context.fillText(alphabet[(drop.offset + tail) % alphabet.length], drop.x + bend, y);
    }
  });
}

function animateRain(time) {
  rainFrame = 0;
  if (paused || document.hidden || !terminalVisible) return;
  // Cap at 24fps, independent of display refresh rate.
  if (time - lastPaint >= 1000 / 24) {
    paintRain(lastPaint ? Math.min((time - lastPaint) / 1000, .1) : 0);
    lastPaint = time;
  }
  rainFrame = requestAnimationFrame(animateRain);
}

function refreshAnimation() {
  clearTimeout(typeTimer);
  cancelAnimationFrame(rainFrame);
  rainFrame = 0;
  lastPaint = 0;
  document.body.classList.toggle('motion-paused', paused || document.hidden);
  document.dispatchEvent(new Event('proofpage:motionchange'));
  $('workbench').classList.toggle('is-dormant', !terminalVisible);
  syncForest();
  if (paused) renderTerminal(true);
  if (!paused && terminalVisible && !document.hidden) {
    typeNext();
    rainFrame = requestAnimationFrame(animateRain);
  }
}

function updateMotionButton() {
  document.querySelectorAll('[data-motion-toggle]').forEach(button => {
    button.hidden = false;
    button.textContent = paused ? 'Play motion ▷' : 'Pause motion Ⅱ';
    button.setAttribute('aria-pressed', String(paused));
  });
}
document.querySelectorAll('[data-motion-toggle]').forEach(button => button.addEventListener('click', () => {
  paused = !paused;
  if (!paused) characters = 0;
  try { localStorage.setItem('proofpage-site-motion', paused ? 'paused' : 'playing'); } catch {}
  updateMotionButton();
  refreshAnimation();
}));
motion.addEventListener('change', event => {
  paused = event.matches;
  if (paused) $('product-film').pause();
  updateMotionButton();
  refreshAnimation();
});
document.addEventListener('visibilitychange', refreshAnimation);
if (typeof ResizeObserver !== 'undefined') new ResizeObserver(sizeCanvas).observe(canvas);
else window.addEventListener('resize', sizeCanvas);
if (typeof IntersectionObserver !== 'undefined') {
  new IntersectionObserver(entries => {
    terminalVisible = entries[0].isIntersecting;
    refreshAnimation();
  }).observe($('workbench'));
  if (forest) new IntersectionObserver(entries => {
    forestVisible = entries[0].isIntersecting;
    syncForest();
  }).observe(forest);
}
sizeCanvas();
chooseScene('capture');
updateMotionButton();
refreshAnimation();

// Inspect the paper leaves; the artwork never reads files or runs collection.
const forestNotes = {
  web: ['A saved page keeps its original and revisions. Follow the trail when the live web changes.', '/docs/#start', 'Explore capture ↗'],
  pdf: ['Keep the actual PDF, with locally extracted text. Scanned pages use offline OCR when available.', '/docs/#media', 'Explore PDFs ↗'],
  image: ['Save the original PNG, JPEG or WebP. Inspect its extracted text alongside the file it came from.', '/docs/#media', 'Explore images ↗'],
  quote: ['Follow an exact quotation back to a saved passage. A wording match helps you inspect a claim; it does not prove truth.', '/docs/#verify', 'Explore Claim Check ↗']
};
if (forest) {
  forest.querySelectorAll('[data-note]').forEach(button => button.addEventListener('click', () => {
    const note = forestNotes[button.dataset.note];
    if (!note) return;
    forest.dataset.selected = button.dataset.note;
    forest.querySelectorAll('[data-note]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
    $('forest-description').textContent = note[0];
    $('forest-guide').href = note[1];
    $('forest-guide').textContent = note[2];
    if (!paused && !motion.matches && typeof forest.querySelector('.forest-root').animate === 'function') {
      forest.querySelector('.forest-root').animate([{opacity:.6},{opacity:1}], {duration:380});
    }
  }));
  // Pointer input nudges the whole canopy by at most four pixels; never moves a target away.
  forest.addEventListener('pointermove', event => {
    if (paused || motion.matches || event.pointerType !== 'mouse') return;
    const box = forest.getBoundingClientRect();
    forest.style.setProperty('--forest-x', ((event.clientX - box.left) / box.width * 8 - 4).toFixed(1) + 'px');
    forest.style.setProperty('--forest-y', ((event.clientY - box.top) / box.height * 6 - 3).toFixed(1) + 'px');
  });
  forest.addEventListener('pointerleave', () => {
    forest.style.removeProperty('--forest-x');
    forest.style.removeProperty('--forest-y');
  });
}

// Product media always waits for an explicit play action.
const film = $('product-film');
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
  const name = button.dataset.view;
  document.querySelectorAll('[data-view]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  document.querySelectorAll('.app-view').forEach(view => { view.hidden = view.id !== `view-${name}`; });
  if (name !== 'film') film.pause();
}));
$('play-tour').addEventListener('click', async () => {
  if (film.paused) {
    try { await film.play(); } catch { $('play-tour').textContent = 'Use the video controls to play'; }
  } else film.pause();
});
film.addEventListener('play', () => { $('play-tour').textContent = 'Pause tour Ⅱ'; });
film.addEventListener('pause', () => { $('play-tour').textContent = 'Play tour ▷'; });
film.addEventListener('ended', () => { $('play-tour').textContent = 'Replay tour ↻'; });
film.addEventListener('error', () => { document.querySelector('.film-bottom p').textContent = 'Video unavailable. Read the text walkthrough or download the MP4.'; });

// Progressive enhancement: content starts visible, with no scroll hijacking.
if (typeof IntersectionObserver !== 'undefined') {
  const reveals = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      reveals.unobserve(entry.target);
      if (paused || motion.matches || typeof entry.target.animate !== 'function') return;
      entry.target.animate([{ opacity: .55, transform: 'translateY(16px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 650, easing: 'cubic-bezier(.2,.7,.2,1)' });
    });
  }, { threshold: .12 });
  document.querySelectorAll('.reveal').forEach(element => reveals.observe(element));
}
