// Browser entry: state machine (menu / play / relic / over / won / pause), input, HUD, sound.
import { newRun, act, chooseRelic } from './core/engine.js';
import { nextStep } from './core/pathfind.js';
import { RELICS, FLOOR_COUNT, modsOf, PLAYER_BASE } from './core/entities.js';
import { Renderer, createView, consumeEvents } from './render/renderer.js';
import { Sfx } from './audio.js';

const canvas = document.getElementById('game');
const renderer = new Renderer(canvas);
const sfx = new Sfx();
const $ = (id) => document.getElementById(id);
const screenEl = $('screen');
const hudEl = $('hud');
const bannerEl = $('banner');

const params = new URLSearchParams(location.search);
let mode = 'menu';
let G = null;
let view = createView();
let menuG = newRun(4242);
const menuView = createView();
let lastRepeatAt = 0;

window.addEventListener('resize', () => renderer.resize());

// ---------- run lifecycle ----------
function startRun(seed) {
  const s = seed ?? (params.has('seed') ? Number(params.get('seed')) : (Math.random() * 1e9) >>> 0);
  G = newRun(s);
  view = createView();
  mode = 'play';
  screenEl.classList.add('hidden');
  hudEl.classList.remove('hidden');
  banner(`FLOOR 1`, 'Every death becomes an echo');
  sfx.play('select');
  updateHud();
}

function doAction(a) {
  if (mode !== 'play' || !G) return;
  act(G, a);
  if (G.events.some((e) => e.type === 'rewind')) view.anims.clear();
  consumeEvents(view, G, G.events);
  soundFor(G.events);
  if (G.status === 'relic') {
    mode = 'relic';
    showRelicScreen();
  } else if (G.status === 'won') {
    mode = 'won';
    saveBest();
    showEndScreen(true);
  } else if (G.status === 'over') {
    mode = 'over';
    saveBest();
    showEndScreen(false);
  }
  updateHud();
}

function soundFor(events) {
  for (const ev of events) {
    switch (ev.type) {
      case 'move':
        if (ev.unit === 'player') sfx.play('step');
        break;
      case 'hit':
        if (ev.target === 'player') sfx.play('hurt');
        else sfx.play('hit');
        break;
      case 'death':
        sfx.play('kill');
        break;
      case 'echo_lost':
        sfx.play('echo_lost');
        break;
      case 'plate':
        sfx.play('plate');
        break;
      case 'windup':
        sfx.play('windup');
        break;
      case 'charge':
        sfx.play('charge');
        break;
      case 'shot':
        sfx.play('shot');
        break;
      case 'pickup':
        sfx.play('pickup');
        break;
      case 'heal':
        sfx.play('pickup');
        break;
      case 'rewind':
        sfx.play('rewind');
        break;
      case 'loop_lost':
        banner('LOOP BROKEN', 'your life is recorded as an echo');
        sfx.play('hurt');
        break;
      case 'loop_start':
        banner(`LOOP ${ev.attempt}/${modsOf(G.relics).attempts}`, `${G.echoes.length} echo${G.echoes.length === 1 ? '' : 'es'} with you`);
        sfx.play('loop');
        break;
      case 'exit':
        sfx.play('exit');
        break;
      default:
        break;
    }
  }
}

// ---------- screens ----------
function showMenu() {
  mode = 'menu';
  hudEl.classList.add('hidden');
  const best = loadBest();
  screenEl.innerHTML = `
    <div class="card-wrap">
      <h1 class="title">ECHO LOOP</h1>
      <div class="subtitle">Every death becomes an echo. Your past lives walk with you.</div>
      <div class="btn-row">
        <button class="btn primary" id="btn-start">Start run</button>
        <button class="btn" id="btn-sound">Sound: ${sfx.enabled ? 'on' : 'off'}</button>
      </div>
      <div class="howto">
        <b>How it works.</b> Each turn you act, then your echoes replay your recorded moves, then enemies act.
        When you die the loop breaks: the life you just lived becomes an echo and the floor resets.
        Echoes can hit enemies, trigger plates that open gates, and die to any hit.
        Clear floor ${FLOOR_COUNT} to win. Choose one relic after each floor.<br/><br/>
        <b>Enemies:</b> Husk chases, Sniper shoots along lines, Charger telegraphs (!) then charges, Warden summons on floor ${FLOOR_COUNT}.
      </div>
      <div class="best">best: ${best ? `${best.score} pts · floor ${best.floor}` : 'no runs yet'}</div>
    </div>`;
  screenEl.classList.remove('hidden');
  $('btn-start').onclick = () => startRun();
  $('btn-sound').onclick = (e) => {
    sfx.toggle();
    e.target.textContent = `Sound: ${sfx.enabled ? 'on' : 'off'}`;
  };
}

function showRelicScreen() {
  const cards = G.offers
    .map((id, i) => {
      const r = RELICS.find((x) => x.id === id);
      return `<button class="relic-card" data-id="${id}"><div class="key">[${i + 1}]</div><div class="name">${r.name}</div><div class="desc">${r.desc}</div></button>`;
    })
    .join('');
  screenEl.innerHTML = `
    <div class="card-wrap">
      <h2 class="title" style="font-size:34px">FLOOR ${G.floor} CLEARED</h2>
      <div class="subtitle">Choose a relic for the descent. Press 1, 2 or 3.</div>
      <div class="cards">${cards}</div>
    </div>`;
  screenEl.classList.remove('hidden');
  screenEl.querySelectorAll('.relic-card').forEach((b) => (b.onclick = () => pickRelic(b.dataset.id)));
  sfx.play('exit');
}

function pickRelic(id) {
  if (mode !== 'relic' || !G.offers.includes(id)) return;
  chooseRelic(G, id);
  view = createView();
  mode = 'play';
  screenEl.classList.add('hidden');
  sfx.play('relic');
  banner(`FLOOR ${G.floor}`, `relic: ${RELICS.find((r) => r.id === id).name}`);
  updateHud();
}

function showEndScreen(won) {
  const s = scoreOf(G);
  const r = G.relics.map((id) => RELICS.find((x) => x.id === id).name).join(', ') || 'none';
  screenEl.innerHTML = `
    <div class="card-wrap">
      <h1 class="title" style="font-size:44px">${won ? 'VICTORY' : 'LOOPS EXHAUSTED'}</h1>
      <div class="subtitle">${won ? 'The Warden falls. The loop is broken for good.' : `The floor ${G.floor} loop closed for the last time.`}</div>
      <div class="stats">
        floor reached <b>${G.floor}</b> · floors cleared <b>${G.clearedFloors}</b> · kills <b>${G.kills}</b><br/>
        score <b>${s}</b><br/>
        relics: ${r}
      </div>
      <div class="btn-row"><button class="btn primary" id="btn-again">New run (N)</button><button class="btn" id="btn-menu">Menu</button></div>
    </div>`;
  screenEl.classList.remove('hidden');
  $('btn-again').onclick = () => startRun();
  $('btn-menu').onclick = () => showMenu();
  sfx.play(won ? 'exit' : 'gameover');
}

function showPause() {
  mode = 'pause';
  screenEl.innerHTML = `
    <div class="card-wrap">
      <h2 class="title" style="font-size:34px">PAUSED</h2>
      <div class="btn-row" style="margin-top:20px">
        <button class="btn primary" id="btn-resume">Resume (Esc)</button>
        <button class="btn" id="btn-new">New run (N)</button>
        <button class="btn" id="btn-menu2">Menu</button>
      </div>
    </div>`;
  screenEl.classList.remove('hidden');
  $('btn-resume').onclick = () => resume();
  $('btn-new').onclick = () => startRun();
  $('btn-menu2').onclick = () => showMenu();
}

function resume() {
  if (mode !== 'pause') return;
  mode = 'play';
  screenEl.classList.add('hidden');
}

// ---------- scoring / persistence ----------
export function scoreOf(g) {
  return g.clearedFloors * 300 + g.kills * 20 + (g.status === 'won' ? 1000 : 0);
}
function saveBest() {
  const cur = { score: scoreOf(G), floor: G.floor };
  const best = loadBest();
  if (!best || cur.score > best.score) localStorage.setItem('echoloop.best', JSON.stringify(cur));
}
function loadBest() {
  try {
    return JSON.parse(localStorage.getItem('echoloop.best'));
  } catch {
    return null;
  }
}

// ---------- HUD ----------
function updateHud() {
  if (!G || mode === 'menu') return;
  const m = modsOf(G.relics);
  $('floor').textContent = G.floor;
  $('attempt').textContent = Math.min(G.attemptsUsed + 1, m.attempts);
  $('attempts').textContent = m.attempts;
  const hp = Math.max(0, G.player.hp);
  const full = '♥'.repeat(hp);
  const empty = '♡'.repeat(Math.max(0, G.player.maxHp - hp));
  $('hp-bar').textContent = full + empty;
  $('hp-num').textContent = `${hp}/${G.player.maxHp}`;
  $('shards').textContent = G.player.shards;
  $('potions').textContent = G.player.potions;
  $('seed').textContent = G.seed;
  $('echo-count').textContent = `${G.echoes.length}/${m.maxEchoes}`;
  $('echo-list').innerHTML = G.echoes.length
    ? G.echoes
        .map((e, i) => `<div class="echo-item"><span>echo ${i + 1}</span><span class="steps">${e.path.length} steps · ${e.cursor % Math.max(1, e.path.length)}/${e.path.length}</span></div>`)
        .join('')
    : '<div class="dim small">none yet. Die to create one.</div>';
  $('relic-list').textContent = G.relics.length ? G.relics.map((id) => RELICS.find((r) => r.id === id).name).join(' · ') : 'none';
  const logEl = $('log');
  logEl.innerHTML = G.log
    .slice(-6)
    .reverse()
    .map((l) => `<div class="entry">${escapeHtml(l)}</div>`)
    .join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

let bannerTimer = null;
function banner(title, sub = '') {
  bannerEl.classList.remove('hidden');
  bannerEl.innerHTML = `${title}${sub ? `<small>${escapeHtml(sub)}</small>` : ''}`;
  bannerEl.style.animation = 'none';
  void bannerEl.offsetWidth;
  bannerEl.style.animation = '';
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => bannerEl.classList.add('hidden'), 1900);
}

// ---------- input ----------
const MOVES = {
  ArrowUp: [0, -1], KeyW: [0, -1],
  ArrowDown: [0, 1], KeyS: [0, 1],
  ArrowLeft: [-1, 0], KeyA: [-1, 0],
  ArrowRight: [1, 0], KeyD: [1, 0],
};

window.addEventListener('keydown', (e) => {
  if (e.code === 'KeyM') {
    sfx.toggle();
    return;
  }
  if (mode === 'menu') {
    if (e.code === 'Enter' || e.code === 'Space') {
      e.preventDefault();
      startRun();
    }
    return;
  }
  if (mode === 'relic') {
    const idx = { Digit1: 0, Digit2: 1, Digit3: 2 }[e.code];
    if (idx !== undefined && G.offers[idx]) pickRelic(G.offers[idx]);
    return;
  }
  if (mode === 'over' || mode === 'won') {
    if (e.code === 'KeyN' || e.code === 'Enter') startRun();
    return;
  }
  if (mode === 'pause') {
    if (e.code === 'Escape') resume();
    else if (e.code === 'KeyN') startRun();
    return;
  }
  if (mode !== 'play') return;
  if (e.code === 'Escape') {
    showPause();
    return;
  }
  const mv = MOVES[e.code];
  if (mv) {
    e.preventDefault();
    if (e.repeat) {
      const now = performance.now();
      if (now - lastRepeatAt < 90) return;
      lastRepeatAt = now;
    }
    doAction({ type: 'move', dx: mv[0], dy: mv[1] });
    return;
  }
  if (e.code === 'Space' || e.code === 'Period' || e.code === 'Numpad5') {
    e.preventDefault();
    if (!e.repeat) doAction({ type: 'wait' });
    return;
  }
  if (e.code === 'KeyR' && !e.repeat) doAction({ type: 'rewind' });
  if (e.code === 'KeyF' && !e.repeat) doAction({ type: 'potion' });
});

canvas.addEventListener('click', (e) => {
  if (mode !== 'play' || !G) return;
  const t = renderer.tileAt(e.clientX, e.clientY);
  if (!t) return;
  if (t.x === G.player.x && t.y === G.player.y) {
    doAction({ type: 'wait' });
    return;
  }
  // click-to-step: take one step along the shortest path (through enemies = attack)
  const step = nextStep(G, G.player, t, null, 1000);
  if (step) doAction({ type: 'move', dx: step.x - G.player.x, dy: step.y - G.player.y });
});

// ---------- main loop ----------
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  renderer.ctx.setTransform(1, 0, 0, 1, 0, 0);
  if (mode === 'menu') {
    renderer.draw(menuG, menuView, dt);
  } else if (G) {
    renderer.draw(G, view, dt);
  }
  requestAnimationFrame(frame);
}

// expose a small handle for automated checks / screenshots
window.echoLoop = {
  get G() {
    return G;
  },
  get mode() {
    return mode;
  },
  act: (a) => doAction(a),
  startRun,
  pickRelic,
};

showMenu();
requestAnimationFrame(frame);
