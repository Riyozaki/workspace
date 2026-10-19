// @ts-check
/**
 * Keyboard shortcut registry. Bindings are strings such as "Ctrl+Shift+Z" or "1".
 * Normalisation makes "shift+ctrl+z" and "Ctrl+Shift+Z" equivalent, and the
 * registry refuses duplicate bindings so two actions can never fight for a key.
 */

const MODIFIER_ORDER = ['Ctrl', 'Alt', 'Shift', 'Meta'];
/** @type {Record<string, string>} */
const ALIASES = { control: 'Ctrl', ctrl: 'Ctrl', alt: 'Alt', option: 'Alt', shift: 'Shift', meta: 'Meta', cmd: 'Meta', command: 'Meta' };

export class HotkeyError extends Error {
  /** @param {string} message */
  constructor(message) { super(message); this.name = 'HotkeyError'; }
}

/**
 * @param {string} binding
 * @returns {string} canonical form, e.g. "Ctrl+Shift+Z"
 */
export function normalizeBinding(binding) {
  const parts = binding.split('+').map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) throw new HotkeyError('Пустое сочетание клавиш.');
  const mods = new Set();
  let key = '';
  for (const part of parts) {
    const alias = ALIASES[part.toLowerCase()];
    if (alias) mods.add(alias);
    else if (key) throw new HotkeyError(`В сочетании «${binding}» больше одной основной клавиши.`);
    else key = part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1).toLowerCase();
  }
  if (!key) throw new HotkeyError(`В сочетании «${binding}» нет основной клавиши.`);
  return [...MODIFIER_ORDER.filter((m) => mods.has(m)), key].join('+');
}

/**
 * @param {{ key: string, ctrlKey?: boolean, altKey?: boolean, shiftKey?: boolean, metaKey?: boolean }} ev
 * @returns {string|null} canonical binding of a browser KeyboardEvent-like object
 */
export function bindingFromEvent(ev) {
  if (['Control', 'Alt', 'Shift', 'Meta'].includes(ev.key)) return null;
  const mods = [];
  if (ev.ctrlKey) mods.push('Ctrl');
  if (ev.altKey) mods.push('Alt');
  if (ev.shiftKey) mods.push('Shift');
  if (ev.metaKey) mods.push('Meta');
  const key = ev.key.length === 1 ? ev.key.toUpperCase() : ev.key;
  return [...mods, key].join('+');
}

export class HotkeyRegistry {
  constructor() {
    /** @type {Map<string, { action: string, binding: string }>} */
    this.byBinding = new Map();
    /** @type {Map<string, string>} action -> binding */
    this.byAction = new Map();
  }

  /**
   * @param {string} action @param {string} binding
   * @throws {HotkeyError} when the binding is already used by another action
   */
  bind(action, binding) {
    const canonical = normalizeBinding(binding);
    const owner = this.byBinding.get(canonical);
    if (owner && owner.action !== action) {
      throw new HotkeyError(`Сочетание ${canonical} уже назначено действию «${owner.action}».`);
    }
    const previous = this.byAction.get(action);
    if (previous) this.byBinding.delete(previous);
    this.byAction.set(action, canonical);
    this.byBinding.set(canonical, { action, binding: canonical });
    return canonical;
  }

  /** @param {string} binding @returns {string|null} action name */
  resolve(binding) {
    return this.byBinding.get(binding)?.action ?? null;
  }

  /** @returns {Array<{action:string, binding:string}>} */
  list() {
    return [...this.byAction.entries()].map(([action, binding]) => ({ action, binding }));
  }
}

/** Default bindings for the studio. */
export const DEFAULT_BINDINGS = {
  'scene.1': '1', 'scene.2': '2', 'scene.3': '3', 'scene.4': '4', 'scene.5': '5',
  'record.toggle': 'Ctrl+R',
  'stream.toggle': 'Ctrl+Shift+S',
  'edit.undo': 'Ctrl+Z',
  'edit.redo': 'Ctrl+Shift+Z',
  'source.delete': 'Delete',
  'source.nudge-left': 'ArrowLeft', 'source.nudge-right': 'ArrowRight',
  'source.nudge-up': 'ArrowUp', 'source.nudge-down': 'ArrowDown',
  'source.nudge-left-fast': 'Shift+ArrowLeft', 'source.nudge-right-fast': 'Shift+ArrowRight',
  'source.nudge-up-fast': 'Shift+ArrowUp', 'source.nudge-down-fast': 'Shift+ArrowDown',
  'project.save': 'Ctrl+S',
};

/** @returns {HotkeyRegistry} */
export function createDefaultHotkeys() {
  const reg = new HotkeyRegistry();
  for (const [action, binding] of Object.entries(DEFAULT_BINDINGS)) reg.bind(action, binding);
  return reg;
}
