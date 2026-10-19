#!/usr/bin/env node
// @ts-check
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { existsSync } from 'node:fs';
import { createDefaultProject, ProjectStore, ModelError } from '../src/model.js';
import { loadProject } from '../src/persistence.js';
import { Engine } from '../src/engine.js';
import { createAppServer } from '../src/server.js';
import { resolveFfmpeg } from '../src/ffmpeg.js';

const here = dirname(fileURLToPath(import.meta.url));
const args = parseArgs(process.argv.slice(2));
const port = Number(args.port ?? process.env.PORT ?? 8080);
const projectPath = resolve(args.project ?? process.env.STUDIO_PROJECT ?? join(here, '..', 'projects', 'default.json'));
const outputDir = resolve(args.out ?? process.env.STUDIO_OUTPUT ?? join(here, '..', 'recordings'));
// Local-only by default: the API can read any file path it is given, so it must
// not be reachable from the network unless the user asks for it explicitly.
const host = args.host ?? process.env.STUDIO_HOST ?? '127.0.0.1';

const ffmpegPath = await resolveFfmpeg(process.env.STUDIO_FFMPEG);
if (!ffmpegPath) {
  console.warn('ffmpeg не найден: предпросмотр работает, запись и трансляция недоступны. Укажите STUDIO_FFMPEG.');
}

let project;
if (existsSync(projectPath)) {
  try {
    project = await loadProject(projectPath);
  } catch (err) {
    if (!(err instanceof ModelError)) throw err;
    console.error(`${err.message}\nЗапуск с пустым проектом; исходный файл не перезаписан.`);
    project = createDefaultProject();
  }
} else {
  project = createDefaultProject();
}

const store = new ProjectStore(project);
const engine = new Engine({ store, ffmpegPath: ffmpegPath ?? 'ffmpeg', outputDir, baseline: process.env.STUDIO_BASELINE === '1' });
const ctx = { store, engine, projectPath };
engine.start();
await engine.prepareActiveScene();

const server = createAppServer({ ctx, publicDir: join(here, '..', 'public') });
server.on('error', (err) => {
  const e = /** @type {NodeJS.ErrnoException} */ (err);
  if (e.code === 'EADDRINUSE') {
    console.error(`Порт ${port} уже занят. Закройте другой процесс или запустите с --port=<номер>.`);
  } else {
    console.error(`Не удалось открыть порт ${port}: ${e.message}`);
  }
  process.exit(1);
});
server.listen(port, host, () => {
  console.log(`Studio: http://${host === '0.0.0.0' ? 'localhost' : host}:${port}  (проект: ${projectPath}, запись: ${outputDir})`);
  if (host === '0.0.0.0') console.warn('Внимание: сервер доступен из сети без авторизации. Используйте только в доверенной сети.');
});

let closing = false;
async function shutdown() {
  if (closing) return;
  closing = true;
  console.log('Остановка: финализируем запись…');
  await engine.shutdown();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

/** @param {string[]} argv */
function parseArgs(argv) {
  /** @type {Record<string, string>} */
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const m = /^--([a-z-]+)(?:=(.*))?$/.exec(argv[i]);
    if (m) out[m[1]] = m[2] ?? argv[++i];
  }
  return out;
}
