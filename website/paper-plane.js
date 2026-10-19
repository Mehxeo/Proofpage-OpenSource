'use strict';

// A folded note drifts through the page as it scrolls. No cursor tracking.
(() => {
  const layer = document.getElementById('paper-aircraft');
  const plane = document.getElementById('paper-airplane');
  const trail = document.querySelector('#flight-trail path');
  const heading = document.querySelector('.hero-heading');
  const canopy = document.querySelector('.forest-canopy');
  const throwButton = document.getElementById('throw-plane');
  if (!layer || !plane || !trail || !heading || !canopy || !throwButton) return;

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  let frame = 0;
  let lastTime = 0;
  let x = 0, y = 0, angle = -18;
  let positioned = false;
  let started = false;
  let launch = null;
  let points = [];
  let lastSample = 0;

  layer.classList.add('is-enhanced');

  function parkedPosition() {
    const box = canopy.getBoundingClientRect();
    return {x: box.left + box.width * .52, y: box.top + box.height * .43};
  }

  function scrollPosition() {
    const home = parkedPosition();
    const departure = clamp(scrollY / Math.max(innerHeight * .8, 480), 0, 1);
    const blend = departure ** 2 * (3 - 2 * departure);
    const phase = scrollY / Math.max(innerHeight, 640);
    // An independent meandering flight path, carried by the page rather than a mouse.
    const floating = {
      x: innerWidth * (.5 + .42 * Math.cos(phase * 1.1)),
      y: innerHeight * (.34 + .15 * Math.sin(phase * .85))
    };
    return {
      x: clamp(home.x * (1 - blend) + floating.x * blend, 48, innerWidth - 48),
      y: clamp(home.y * (1 - blend) + floating.y * blend, 60, innerHeight - 48)
    };
  }

  function canFly() {
    return !reduced.matches && !document.hidden && !document.body.classList.contains('motion-paused');
  }

  function visibleAtRest() {
    const box = heading.getBoundingClientRect();
    return box.bottom > 0 && box.top < innerHeight;
  }

  function draw(bank = 0) {
    plane.style.transform = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0) rotate(${angle.toFixed(2)}deg)`;
    plane.style.setProperty('--plane-bank', `${bank.toFixed(2)}deg`);
  }

  function clearTrail() {
    points = [];
    trail.setAttribute('d', '');
    layer.classList.add('is-settled');
  }

  function wake() {
    if (!frame && canFly()) {
      lastTime = 0;
      frame = requestAnimationFrame(fly);
    }
  }

  function throwPlane() {
    if (!canFly()) return;
    const box = heading.getBoundingClientRect();
    const end = scrollPosition();
    const top = clamp(box.top, 90, innerHeight * .35);
    launch = {
      elapsed: 0,
      start: {x: -75, y: top + 200},
      a: {x: innerWidth * .25, y: Math.max(60, top - 140)},
      b: {x: Math.min(innerWidth - 30, end.x + 220), y: Math.max(65, top - 25)},
      end
    };
    started = true;
    clearTrail();
    wake();
  }

  function fly(time) {
    frame = 0;
    if (!canFly()) return;
    const delta = lastTime ? Math.min((time - lastTime) / 1000, .04) : 1 / 60;
    lastTime = time;
    const previousX = x, previousY = y;
    let targetAngle = angle;

    if (launch) {
      launch.elapsed += delta;
      const progress = Math.min(1, launch.elapsed / 2.3);
      const t = 1 - Math.pow(1 - progress, 1.7);
      const s = 1 - t;
      const {start, a, b, end} = launch;
      x = s ** 3 * start.x + 3 * s ** 2 * t * a.x + 3 * s * t ** 2 * b.x + t ** 3 * end.x;
      y = s ** 3 * start.y + 3 * s ** 2 * t * a.y + 3 * s * t ** 2 * b.y + t ** 3 * end.y;
      const dx = 3 * s ** 2 * (a.x - start.x) + 6 * s * t * (b.x - a.x) + 3 * t ** 2 * (end.x - b.x);
      const dy = 3 * s ** 2 * (a.y - start.y) + 6 * s * t * (b.y - a.y) + 3 * t ** 2 * (end.y - b.y);
      targetAngle = Math.atan2(dy, dx) * 180 / Math.PI;
      if (progress === 1) launch = null;
    } else {
      const target = scrollPosition();
      const dx = target.x - x, dy = target.y - y;
      const distance = Math.hypot(dx, dy);
      const step = Math.min(1 - Math.exp(-delta * 4.3), 620 * delta / Math.max(distance, 1));
      x += dx * step;
      y += dy * step;
      targetAngle = distance > 3 ? Math.atan2(dy, dx) * 180 / Math.PI : -18;
    }

    const turn = ((targetAngle - angle + 180) % 360 + 360) % 360 - 180;
    angle = ((angle + turn * (1 - Math.exp(-delta * 8)) + 180) % 360 + 360) % 360 - 180;
    draw(clamp(turn * -.35, -24, 24));
    positioned = true;
    if (time - lastSample > 30) {
      points.push({x, y, time});
      lastSample = time;
    }
    points = points.filter(point => time - point.time < 650).slice(-24);
    trail.setAttribute('d', points.map((point, index) => `${index ? 'L' : 'M'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' '));
    const moving = Boolean(launch) || Math.hypot(x - previousX, y - previousY) > .08 || Math.abs(turn) > .2;
    layer.classList.toggle('is-settled', !moving);
    if (moving) frame = requestAnimationFrame(fly);
    else plane.style.setProperty('--plane-bank', '0deg');
  }

  function sync() {
    const allowed = canFly();
    throwButton.hidden = reduced.matches;
    throwButton.disabled = !allowed;
    throwButton.title = allowed ? 'Send the paper airplane around again' : 'Play motion to throw the plane';
    layer.hidden = document.hidden || (reduced.matches && !visibleAtRest());
    if (!positioned || reduced.matches) {
      ({x, y} = reduced.matches ? parkedPosition() : scrollPosition());
      angle = -18;
      draw();
      positioned = true;
    }
    if (!allowed) {
      cancelAnimationFrame(frame);
      frame = 0;
      lastTime = 0;
      clearTrail();
    } else if (!started) throwPlane();
    else wake();
  }

  throwButton.addEventListener('click', throwPlane);
  window.addEventListener('scroll', () => {
    if (reduced.matches) {
      ({x, y} = parkedPosition());
      draw();
    }
    sync();
  }, {passive: true});
  window.addEventListener('resize', () => { launch = null; sync(); }, {passive: true});
  document.addEventListener('visibilitychange', sync);
  document.addEventListener('proofpage:motionchange', sync);
  reduced.addEventListener('change', () => { launch = null; sync(); });
  sync();
})();
