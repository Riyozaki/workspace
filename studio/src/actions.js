// @ts-check
/**
 * Command layer: every user-visible operation (HTTP API, hotkeys, UI buttons)
 * goes through `dispatch`, so validation and error messages live in one place.
 */
import { ModelError } from './model.js';
import { EncoderError } from './encoder.js';
import { loadProject, saveProject } from './persistence.js';
import { access } from 'node:fs/promises';

/** @param {string} path */
async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

export class CommandError extends Error {
  /** @param {string} message @param {string} [code] */
  constructor(message, code = 'bad-command') { super(message); this.name = 'CommandError'; this.code = code; }
}

/**
 * @param {{ store: import('./model.js').ProjectStore, engine: import('./engine.js').Engine, projectPath?: string }} ctx
 * @param {string} type
 * @param {Record<string, any>} [args]
 * @returns {Promise<any>}
 */
export async function dispatch(ctx, type, args = {}) {
  const { store, engine } = ctx;
  // The encoder and the file name both depend on the format; reject unknown ones here.
  if ('format' in args && !['mp4', 'mkv', 'webm'].includes(args.format)) throw new CommandError(`Неизвестный формат записи: ${args.format}.`, 'bad-format');
  const p = store.project;
  try {
    switch (type) {
      case 'scene.switch': {
        const id = sceneIdAt(store, args);
        store.setActiveScene(id);
        return { activeSceneId: id };
      }
      case 'scene.add': return { id: store.addScene(args.name) };
      case 'scene.remove': store.removeScene(String(args.sceneId)); return {};
      case 'source.add': {
        const kind = args.kind;
        if (!['color', 'image', 'text', 'video'].includes(kind)) throw new CommandError('Неизвестный тип источника.');
        if (kind === 'image' && !args.path) throw new CommandError('Укажите путь к изображению.');
        if (kind === 'video' && !args.path) throw new CommandError('Укажите путь к видеофайлу.');
        if ((kind === 'image' || kind === 'video') && !(await fileExists(String(args.path)))) {
          throw new CommandError(`Файл не найден: ${args.path}. Проверьте путь.`, 'file-not-found');
        }
        const sceneId = args.sceneId ?? store.project.activeSceneId;
        return { id: store.addSource(sceneId, { ...args, kind }) };
      }
      case 'source.remove': store.removeSource(String(args.sceneId), String(args.sourceId)); return {};
      case 'source.move': store.moveSource(String(args.sceneId), String(args.sourceId), args.dir === -1 ? -1 : 1); return {};
      case 'source.update': store.updateSource(String(args.sceneId), String(args.sourceId), args.patch ?? {}); return {};
      case 'edit.undo': return { changed: store.undo() };
      case 'edit.redo': return { changed: store.redo() };
      case 'record.start': return { output: await engine.startRecording(args.format ?? 'mp4') };
      case 'record.stop':
        if (!engine.recorder) throw new CommandError('Запись сейчас не идёт.', 'not-recording');
        return { result: await engine.stopRecording() };
      case 'record.toggle': {
        if (engine.recorder) return { result: await engine.stopRecording() };
        return { output: await engine.startRecording(args.format ?? 'mp4') };
      }
      case 'stream.start': await engine.startStream(String(args.url ?? ''), Number(args.bitrateKbps) || 3000); return {};
      case 'stream.stop':
        if (!engine.stream) throw new CommandError('Трансляция сейчас не идёт.', 'not-streaming');
        return { result: await engine.stopStream() };
      case 'stream.toggle': {
        if (engine.stream) return { result: await engine.stopStream() };
        await engine.startStream(String(args.url ?? ''), Number(args.bitrateKbps) || 3000);
        return {};
      }
      case 'project.set-canvas': {
        const width = Number(args.width) || p.canvas.width;
        const height = Number(args.height) || p.canvas.height;
        const fps = Number(args.fps) || p.canvas.fps;
        // Same rule as the encoder (yuv420p needs even sides), but rejected at the moment of the change.
        if (width % 2 || height % 2) throw new CommandError(`Размер ${width}×${height} должен быть чётным (требование H.264/VP9).`, 'bad-size');
        store.update((d) => { d.canvas = { width, height, fps }; });
        return {};
      }
      case 'project.save': {
        if (!ctx.projectPath) throw new CommandError('Путь к файлу проекта не задан.');
        await saveProject(ctx.projectPath, store.project);
        store.markSaved();
        return { path: ctx.projectPath };
      }
      case 'project.load': {
        const path = String(args.path ?? ctx.projectPath ?? '');
        if (!path) throw new CommandError('Укажите путь к файлу проекта.');
        const loaded = await loadProject(path);
        store.update((d) => Object.assign(d, loaded), { record: true });
        store.markSaved();
        ctx.projectPath = path;
        return { path };
      }
      case 'status': return { status: engine.status() };
      default:
        throw new CommandError(`Неизвестная команда «${type}».`);
    }
  } catch (err) {
    if (err instanceof ModelError || err instanceof EncoderError || err instanceof CommandError) {
      // Model errors are validation failures; the others carry their own code.
      const code = err instanceof ModelError ? 'invalid' : /** @type {any} */ (err).code ?? 'error';
      throw new CommandError(err.message, code);
    }
    throw err;
  }
}

/** @param {import('./model.js').ProjectStore} store @param {Record<string, any>} args */
function sceneIdAt(store, args) {
  if (args.sceneId) return String(args.sceneId);
  if (typeof args.index === 'number') {
    const s = store.project.scenes[args.index];
    if (!s) throw new CommandError(`Сцены с номером ${args.index + 1} нет.`);
    return s.id;
  }
  throw new CommandError('Не указана сцена.');
}
