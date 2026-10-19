// Browser UI. Talks to the JSON API only; no business rules live here.
import { bindingFromEvent } from '/shared/hotkeys.js';
const $ = (sel) => document.querySelector(sel);
const state = { project: null, selectedId: null, status: null, bindings: {}, busy: false };

/** Sends a command and updates state. Errors are shown to the user, not thrown. */
async function call(type, args = {}) {
  state.busy = true;
  try {
    const res = await fetch('/api/command', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, args }),
    });
    const body = await res.json().catch(() => ({ error: 'Сервер вернул непонятный ответ.' }));
    if (!res.ok) { say(body.error || `Ошибка ${res.status}`, true); return null; }
    if (body.project) { state.project = body.project; render(); }
    say('');
    return body.result ?? {};
  } catch {
    say('Нет связи с сервером. Проверьте, что Studio запущен.', true);
    return null;
  } finally {
    state.busy = false;
  }
}

/** @param {string} text @param {boolean} [isError] */
function say(text, isError = false) {
  const el = $('#status');
  el.textContent = text;
  el.classList.toggle('error', isError);
}

function activeScene() {
  return state.project.scenes.find((s) => s.id === state.project.activeSceneId);
}

function selectedSource() {
  return activeScene().items.find((i) => i.id === state.selectedId) ?? null;
}

function render() {
  renderScenes();
  renderSources();
  renderProps();
  renderButtons();
}

function renderScenes() {
  const ol = $('#scenes');
  ol.replaceChildren(...state.project.scenes.map((s, i) => {
    const li = document.createElement('li');
    li.tabIndex = 0;
    li.setAttribute('role', 'button');
    li.setAttribute('aria-pressed', String(s.id === state.project.activeSceneId));
    li.classList.toggle('active', s.id === state.project.activeSceneId);
    li.innerHTML = `<span class="name"></span><button type="button" aria-label="Удалить сцену"></button>`;
    li.querySelector('.name').textContent = `${i + 1}. ${s.name}`;
    li.querySelector('button').textContent = '✕';
    li.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      call('scene.switch', { sceneId: s.id });
    });
    li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); call('scene.switch', { sceneId: s.id }); } });
    li.querySelector('button').addEventListener('click', () => {
      if (state.project.scenes.length === 1) return say('Нельзя удалить последнюю сцену.', true);
      if (confirm(`Удалить сцену «${s.name}»?`)) call('scene.remove', { sceneId: s.id });
    });
    return li;
  }));
}

function renderSources() {
  const ul = $('#sources');
  const scene = activeScene();
  const items = [...scene.items].reverse(); // top of the list = front of the z-order
  ul.replaceChildren(...items.map((it) => {
    const li = document.createElement('li');
    li.tabIndex = 0;
    li.setAttribute('aria-selected', String(it.id === state.selectedId));
    li.innerHTML = `<button type="button" class="vis"></button><span class="name"></span>
      <button type="button" class="up" aria-label="Выше по слоям">▲</button>
      <button type="button" class="down" aria-label="Ниже по слоям">▼</button>
      <button type="button" class="del" aria-label="Удалить источник">✕</button>`;
    const label = { color: 'цвет', text: 'текст', image: 'изображение', video: 'видео' }[it.kind];
    li.querySelector('.name').textContent = `${it.name} (${label})`;
    const vis = li.querySelector('.vis');
    vis.textContent = it.visible ? '👁' : '—';
    vis.setAttribute('aria-label', it.visible ? 'Скрыть источник' : 'Показать источник');
    vis.addEventListener('click', (e) => { e.stopPropagation(); call('source.update', { sceneId: scene.id, sourceId: it.id, patch: { visible: !it.visible } }); });
    li.querySelector('.up').addEventListener('click', (e) => { e.stopPropagation(); call('source.move', { sceneId: scene.id, sourceId: it.id, dir: 1 }); });
    li.querySelector('.down').addEventListener('click', (e) => { e.stopPropagation(); call('source.move', { sceneId: scene.id, sourceId: it.id, dir: -1 }); });
    li.querySelector('.del').addEventListener('click', (e) => { e.stopPropagation(); removeSelected(it.id); });
    li.addEventListener('click', () => { state.selectedId = it.id; render(); });
    li.addEventListener('keydown', (e) => { if (e.key === 'Enter') { state.selectedId = it.id; render(); } });
    return li;
  }));
}

function renderProps() {
  const form = $('#props');
  const it = selectedSource();
  if (!it) {
    form.replaceChildren(Object.assign(document.createElement('p'), { className: 'hint', id: 'props-empty', textContent: 'Выберите источник в списке.' }));
    return;
  }
  const fields = [
    ['x', 'X', 'number', it.x], ['y', 'Y', 'number', it.y],
    ['w', 'Ширина', 'number', it.w], ['h', 'Высота', 'number', it.h],
  ];
  if (it.kind === 'color') fields.push(['color', 'Цвет', 'color', it.color]);
  if (it.kind === 'text') fields.push(['text', 'Текст', 'text', it.text ?? ''], ['color', 'Цвет текста', 'color', it.color]);
  if (it.kind === 'image' || it.kind === 'video') fields.push(['path', 'Путь к файлу', 'text', it.path ?? '']);
  const nodes = fields.map(([key, label, type, value]) => {
    const l = document.createElement('label');
    l.textContent = label;
    const input = document.createElement('input');
    input.type = type; input.name = key; input.value = value;
    if (type === 'number') { input.step = '1'; input.inputMode = 'numeric'; }
    input.addEventListener('change', () => {
      const v = type === 'number' ? Number(input.value) : input.value;
      call('source.update', { sceneId: activeScene().id, sourceId: it.id, patch: { [key]: v } });
    });
    l.append(input);
    return l;
  });
  form.replaceChildren(...nodes);
}

function renderButtons() {
  const s = state.status;
  const rec = !!s?.recording;
  const stream = !!s?.streaming;
  // Without ffmpeg, say why up front instead of failing after a click.
  const noFfmpeg = s && s.ffmpeg && !s.ffmpeg.available;
  const why = 'ffmpeg не найден. Укажите путь переменной STUDIO_FFMPEG и перезапустите Studio.';
  for (const id of ['#btn-record', '#btn-stream']) {
    const btn = $(id);
    const active = btn.getAttribute('aria-pressed') === 'true';
    // A running output can always be stopped; only starting is blocked.
    btn.disabled = !!noFfmpeg && !active;
    btn.title = noFfmpeg && !active ? why : btn.dataset.hint;
  }
  const recBtn = $('#btn-record');
  recBtn.textContent = rec ? '■ Остановить запись' : '● Запись';
  recBtn.setAttribute('aria-pressed', String(rec));
  const sBtn = $('#btn-stream');
  sBtn.textContent = stream ? '■ Остановить стрим' : 'Старт стрима';
  sBtn.setAttribute('aria-pressed', String(stream));
  $('#fps').textContent = s ? `FPS ${s.fps} · кадр ${s.renderMsLast} мс · пропущено ${s.lateFrames + s.encoderDropped}` : '';
}

async function removeSelected(id) {
  if (!id) return;
  call('source.remove', { sceneId: activeScene().id, sourceId: id });
  if (state.selectedId === id) state.selectedId = null;
}

// ----- status + preview loops -----
// Status polling is silent: it must not clear messages the user is reading.
async function pollStatus() {
  try {
    const res = await fetch('/api/command', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'status' }),
    });
    const body = await res.json();
    if (body.ok) {
      state.status = body.result.status;
      state.dirty = body.result.status.dirty;
      renderButtons();
      if (state.status.lastError) say(state.status.lastError, true);
    }
  } catch {
    // Connection problems are reported by user-initiated actions; keep polling quietly.
  }
  setTimeout(pollStatus, 500);
}

function pollPreview() {
  const img = $('#preview');
  const next = new Image();
  next.onload = () => { img.src = next.src; setTimeout(pollPreview, 100); };
  next.onerror = () => setTimeout(pollPreview, 500);
  next.src = `/api/preview.jpg?t=${Date.now()}`;
}

// ----- actions & forms -----
$('#btn-undo').addEventListener('click', () => call('edit.undo'));
$('#btn-redo').addEventListener('click', () => call('edit.redo'));
$('#btn-save').addEventListener('click', async () => { const r = await call('project.save'); if (r) { state.dirty = false; say('Проект сохранён.'); } });
$('#btn-record').addEventListener('click', async () => {
  const r = await call('record.toggle', { format: 'mp4' });
  if (r?.result) say(`Запись сохранена: ${r.result.output} (кадров: ${r.result.framesWritten}, пропущено: ${r.result.framesDropped})`);
  else if (r?.output) say(`Идёт запись: ${r.output}`);
});
$('#btn-stream').addEventListener('click', async () => {
  const url = $('#stream-url').value.trim();
  const r = await call('stream.toggle', { url });
  if (r && !r.result) say('Трансляция запущена.');
  if (r?.result) say('Трансляция остановлена.');
});
$('#btn-scene-add').addEventListener('click', () => {
  const name = prompt('Название сцены', `Сцена ${state.project.scenes.length + 1}`);
  if (name !== null) call('scene.add', { name });
});
$('#add-source').addEventListener('submit', async (e) => {
  e.preventDefault();
  const kind = $('#src-kind').value;
  const value = $('#src-value').value;
  const args = { kind, name: $('#src-name').value.trim() || undefined, sceneId: activeScene().id };
  if (kind === 'color') args.color = value.trim() || '#336699';
  if (kind === 'text') args.text = value || 'Текст';
  if (kind === 'image' || kind === 'video') args.path = $('#src-path').value.trim();
  const r = await call('source.add', args);
  if (r?.id) { state.selectedId = r.id; $('#add-source').reset(); render(); say('Источник добавлен.'); }
});

// ----- hotkeys -----
const HOTKEY_ACTIONS = {
  'scene.1': () => switchByIndex(0), 'scene.2': () => switchByIndex(1), 'scene.3': () => switchByIndex(2),
  'scene.4': () => switchByIndex(3), 'scene.5': () => switchByIndex(4),
  'record.toggle': () => $('#btn-record').click(),
  'stream.toggle': () => $('#btn-stream').click(),
  'edit.undo': () => call('edit.undo'),
  'edit.redo': () => call('edit.redo'),
  'project.save': () => $('#btn-save').click(),
  'source.delete': () => removeSelected(state.selectedId),
};

function switchByIndex(i) {
  const s = state.project.scenes[i];
  if (s) call('scene.switch', { sceneId: s.id });
}

document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea, select')) {
    // Let text fields keep their own shortcuts (Ctrl+Z inside a field).
    if (!(e.ctrlKey || e.metaKey)) return;
  }
  const binding = bindingFromEvent(e);
  if (!binding) return;
  const action = Object.entries(state.bindings).find(([, b]) => b === binding)?.[0];
  if (!action || !HOTKEY_ACTIONS[action]) return;
  e.preventDefault();
  HOTKEY_ACTIONS[action]();
});

// Warn before leaving with unsaved edits (data-loss protection).
window.addEventListener('beforeunload', (e) => {
  if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
});

async function init() {
  for (const id of ['#btn-record', '#btn-stream']) $(id).dataset.hint = $(id).title;
  state.bindings = await (await fetch('/api/hotkeys')).json();
  $('#help-list').replaceChildren(...Object.entries(state.bindings).map(([a, b]) => {
    const li = document.createElement('li');
    li.textContent = `${b} — ${a}`;
    return li;
  }));
  const project = await (await fetch('/api/project')).json();
  state.project = project;
  state.selectedId = null;
  render();
  pollStatus();
  pollPreview();
}
init();
