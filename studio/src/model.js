// @ts-check
/**
 * Project model: scenes, sources and their placement. Pure data + operations,
 * no I/O, so it is unit-testable and reusable from the server and the CLI.
 *
 * @typedef {'color'|'image'|'text'|'video'} SourceKind
 * @typedef {{ id: string, kind: SourceKind, name: string, visible: boolean,
 *            x: number, y: number, w: number, h: number,
 *            color?: string, path?: string, text?: string, fontSize?: number,
 *            crop: {left:number,top:number,right:number,bottom:number},
 *            rotation: number, opacity: number }} Source
 * @typedef {{ id: string, name: string, items: Source[] }} Scene
 * @typedef {{ version: number, canvas: {width:number,height:number,fps:number},
 *            scenes: Scene[], activeSceneId: string }} Project
 */

export const SCHEMA_VERSION = 2;
export const MAX_SOURCES_PER_SCENE = 64;
export const MAX_UNDO = 200;

const KINDS = new Set(['color', 'image', 'text', 'video']);

export class ModelError extends Error {
  /** @param {string} message */
  constructor(message) {
    super(message);
    this.name = 'ModelError';
  }
}

let idCounter = 0;
/** @param {string} prefix */
export function newId(prefix) {
  idCounter += 1;
  return `${prefix}${Date.now().toString(36)}${idCounter.toString(36)}`;
}

/** @returns {Project} */
export function createDefaultProject() {
  const scene = { id: 'scene-1', name: 'Сцена 1', items: [] };
  return {
    version: SCHEMA_VERSION,
    canvas: { width: 1280, height: 720, fps: 30 },
    scenes: [scene],
    activeSceneId: scene.id,
  };
}

/**
 * Validates and normalises an untrusted object (e.g. a loaded file).
 * Migrates schema v1 (no `visible`, no `fps`) to the current version.
 * @param {unknown} raw
 * @returns {Project}
 */
export function validateProject(raw) {
  if (!raw || typeof raw !== 'object') throw new ModelError('Файл проекта повреждён: ожидался JSON-объект.');
  const o = /** @type {any} */ (raw);
  const canvas = o.canvas ?? {};
  const width = clampInt(canvas.width, 16, 7680, 1280);
  const height = clampInt(canvas.height, 16, 4320, 720);
  const fps = clampInt(canvas.fps, 1, 120, 30);
  if (!Array.isArray(o.scenes) || o.scenes.length === 0) {
    throw new ModelError('В проекте нет ни одной сцены.');
  }
  const scenes = o.scenes.map((/** @type {any} */ s, /** @type {number} */ i) => {
    const items = Array.isArray(s?.items) ? s.items.map((/** @type {unknown} */ it) => normalizeSource(it)) : [];
    if (items.length > MAX_SOURCES_PER_SCENE) {
      throw new ModelError(`В сцене «${s?.name ?? i}» больше ${MAX_SOURCES_PER_SCENE} источников.`);
    }
    return { id: String(s?.id ?? newId('scene-')), name: String(s?.name ?? `Сцена ${i + 1}`), items };
  });
  const ids = new Set(scenes.map((/** @type {{id: string}} */ s) => s.id));
  if (ids.size !== scenes.length) throw new ModelError('В проекте есть сцены с одинаковым id.');
  const activeSceneId = ids.has(o.activeSceneId) ? o.activeSceneId : scenes[0].id;
  return { version: SCHEMA_VERSION, canvas: { width, height, fps }, scenes, activeSceneId };
}

/** @param {unknown} v @param {number} lo @param {number} hi @param {number} dflt */
function clampInt(v, lo, hi, dflt) {
  const n = typeof v === 'number' && Number.isFinite(v) ? Math.round(v) : dflt;
  return Math.min(hi, Math.max(lo, n));
}

/** @param {any} s @returns {Source} */
function normalizeSource(s) {
  const kind = KINDS.has(s?.kind) ? s.kind : 'color';
  return {
    id: String(s?.id ?? newId('src-')),
    kind,
    name: String(s?.name ?? kind),
    visible: s?.visible !== false,
    x: Number(s?.x) || 0,
    y: Number(s?.y) || 0,
    w: Math.max(1, Number(s?.w) || 320),
    h: Math.max(1, Number(s?.h) || 180),
    color: typeof s?.color === 'string' ? s.color : '#336699',
    path: typeof s?.path === 'string' ? s.path : undefined,
    text: typeof s?.text === 'string' ? s.text : undefined,
    fontSize: Number(s?.fontSize) || 48,
    crop: normalizeCrop(s?.crop),
    rotation: Number.isFinite(Number(s?.rotation)) ? ((Number(s.rotation) % 360) + 360) % 360 : 0,
    opacity: Number.isFinite(Number(s?.opacity)) ? Math.min(100, Math.max(0, Number(s.opacity))) : 100,
  };
}

/** @param {any} c @returns {{left:number,top:number,right:number,bottom:number}} */
function normalizeCrop(c) {
  const v = (/** @type {unknown} */ n) => Math.max(0, Math.round(Number.isFinite(Number(n)) ? Number(n) : 0));
  return { left: v(c?.left), top: v(c?.top), right: v(c?.right), bottom: v(c?.bottom) };
}

/**
 * Immutable-style store with undo/redo. Every mutation returns nothing and
 * pushes a snapshot onto the undo stack, so callers never see partial state.
 */
export class ProjectStore {
  /** @param {Project} project */
  constructor(project) {
    /** @type {Project} */
    this.project = project;
    /** @type {Project[]} */
    this.undoStack = [];
    /** @type {Project[]} */
    this.redoStack = [];
    /** @type {Set<(p: Project) => void>} */
    this.listeners = new Set();
    this.dirty = false;
  }

  /** @param {(p: Project) => void} fn */
  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  /** @param {(p: Project) => void} mutate @param {{ record?: boolean }} [opts] */
  update(mutate, opts = {}) {
    const before = structuredClone(this.project);
    const draft = structuredClone(this.project);
    mutate(draft);
    if (opts.record !== false) {
      this.undoStack.push(before);
      if (this.undoStack.length > MAX_UNDO) this.undoStack.shift();
      this.redoStack = [];
    }
    this.project = validateProject(draft);
    this.dirty = true;
    for (const fn of this.listeners) fn(this.project);
  }

  /** @returns {boolean} */
  undo() {
    const prev = this.undoStack.pop();
    if (!prev) return false;
    this.redoStack.push(structuredClone(this.project));
    this.project = prev;
    this.dirty = true;
    for (const fn of this.listeners) fn(this.project);
    return true;
  }

  /** @returns {boolean} */
  redo() {
    const next = this.redoStack.pop();
    if (!next) return false;
    this.undoStack.push(structuredClone(this.project));
    this.project = next;
    this.dirty = true;
    for (const fn of this.listeners) fn(this.project);
    return true;
  }

  /** @returns {Scene} */
  activeScene() {
    const s = this.project.scenes.find((x) => x.id === this.project.activeSceneId);
    if (!s) throw new ModelError('Активная сцена не найдена.');
    return s;
  }

  /** @param {string} sceneId */
  setActiveScene(sceneId) {
    if (!this.project.scenes.some((s) => s.id === sceneId)) throw new ModelError('Сцена не найдена.');
    if (this.project.activeSceneId === sceneId) return;
    // Switching scenes is not an edit: it is not recorded in undo history.
    this.update((p) => { p.activeSceneId = sceneId; }, { record: false });
    this.dirty = false;
  }

  /** @param {string} [name] */
  addScene(name) {
    const id = newId('scene-');
    this.update((p) => {
      p.scenes.push({ id, name: name?.trim() || `Сцена ${p.scenes.length + 1}`, items: [] });
      p.activeSceneId = id;
    });
    return id;
  }

  /** @param {string} sceneId */
  removeScene(sceneId) {
    if (this.project.scenes.length === 1) throw new ModelError('Нельзя удалить последнюю сцену.');
    this.update((p) => {
      p.scenes = p.scenes.filter((s) => s.id !== sceneId);
      if (p.activeSceneId === sceneId) p.activeSceneId = p.scenes[0].id;
    });
  }

  /**
   * @param {string} sceneId
   * @param {{ kind: SourceKind, name?: string } & Partial<Source>} spec
   */
  addSource(sceneId, spec) {
    const id = newId('src-');
    this.update((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId);
      if (!scene) throw new ModelError('Сцена не найдена.');
      if (scene.items.length >= MAX_SOURCES_PER_SCENE) {
        throw new ModelError(`Достигнут лимит: ${MAX_SOURCES_PER_SCENE} источников в сцене.`);
      }
      scene.items.push(normalizeSource({ ...spec, id }));
    });
    return id;
  }

  /** @param {string} sceneId @param {string} sourceId */
  removeSource(sceneId, sourceId) {
    this.update((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId);
      if (!scene) throw new ModelError('Сцена не найдена.');
      scene.items = scene.items.filter((i) => i.id !== sourceId);
    });
  }

  /**
   * Moves a source one step toward the front (+1) or back (-1) of the z-order.
   * Items later in the array are drawn on top.
   * @param {string} sceneId @param {string} sourceId @param {1|-1} dir
   */
  moveSource(sceneId, sourceId, dir) {
    this.update((p) => {
      const items = p.scenes.find((s) => s.id === sceneId)?.items;
      if (!items) throw new ModelError('Сцена не найдена.');
      const i = items.findIndex((x) => x.id === sourceId);
      const j = i + dir;
      if (i < 0) throw new ModelError('Источник не найден.');
      if (j < 0 || j >= items.length) return;
      [items[i], items[j]] = [items[j], items[i]];
    });
  }

  /**
   * Patches fields of a source. Coordinates are clamped to the canvas so a
   * source can never be lost off-screen by a typo.
   * @param {string} sceneId @param {string} sourceId @param {Partial<Source>} patch
   */
  updateSource(sceneId, sourceId, patch) {
    if ('opacity' in patch && !(Number(patch.opacity) >= 0 && Number(patch.opacity) <= 100)) {
      throw new ModelError('Прозрачность должна быть от 0 до 100 %.');
    }
    if ('crop' in patch && patch.crop) {
      for (const side of /** @type {const} */ (['left', 'top', 'right', 'bottom'])) {
        const n = Number(patch.crop[side]);
        if (!Number.isFinite(n) || n < 0) throw new ModelError(`Обрезка «${side}» должна быть неотрицательным числом.`);
      }
    }
    for (const key of /** @type {const} */ (['x', 'y', 'w', 'h'])) {
      /** @type {unknown} */
      const v = patch[key];
      if (key in patch && (v === '' || v === null || !Number.isFinite(Number(v)))) {
        // An empty or non-numeric field must not silently become 0.
        throw new ModelError(`Поле «${key}» должно быть числом.`);
      }
    }
    this.update((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId);
      const item = scene?.items.find((x) => x.id === sourceId);
      if (!item) throw new ModelError('Источник не найден.');
      Object.assign(item, patch);
      item.w = Math.max(1, Math.min(p.canvas.width, Math.round(item.w)));
      item.h = Math.max(1, Math.min(p.canvas.height, Math.round(item.h)));
      item.x = Math.round(Math.min(p.canvas.width - 1, Math.max(-item.w + 1, item.x)));
      item.y = Math.round(Math.min(p.canvas.height - 1, Math.max(-item.h + 1, item.y)));
    });
  }

  markSaved() { this.dirty = false; }
}
