// HTTP-level tests: the JSON API contract and static file safety, on an ephemeral port.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ProjectStore, createDefaultProject } from '../src/model.js';
import { Engine } from '../src/engine.js';
import { createAppServer } from '../src/server.js';

const here = dirname(fileURLToPath(import.meta.url));
let server; let base; let engine;

before(async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-http-'));
  const store = new ProjectStore(createDefaultProject());
  engine = new Engine({ store, ffmpegPath: 'ffmpeg', outputDir: dir });
  const ctx = { store, engine, projectPath: join(dir, 'p.json') };
  server = createAppServer({ ctx, publicDir: join(here, '..', 'public') });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await engine.shutdown();
  await new Promise((r) => server.close(r));
});

const post = (body, raw = false) => fetch(`${base}/api/command`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: raw ? body : JSON.stringify(body),
});

test('GET /api/project returns the current project', async () => {
  const res = await fetch(`${base}/api/project`);
  assert.equal(res.status, 200);
  const p = await res.json();
  assert.equal(p.canvas.width, 1280);
  assert.equal(p.scenes.length, 1);
});

test('POST /api/command runs a command and returns the updated project', async () => {
  const res = await post({ type: 'source.add', args: { kind: 'color', name: 'Фон', color: '#123456' } });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.project.scenes[0].items.at(-1).color, '#123456');
});

test('validation failures are 422 with a Russian message and a code', async () => {
  const res = await post({ type: 'source.add', args: { kind: 'image' } });
  assert.equal(res.status, 422);
  const body = await res.json();
  assert.match(body.error, /путь/);
  assert.equal(body.code, 'bad-command');
});

test('malformed JSON is 400 bad-json; missing type is 400', async () => {
  const bad = await post('{not json', true);
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).code, 'bad-json');
  const noType = await post({ args: {} });
  assert.equal(noType.status, 400);
});

test('preview is 204 until the first frame exists, then a JPEG', async () => {
  const res = await fetch(`${base}/api/preview.jpg`);
  assert.ok(res.status === 204 || res.status === 200);
  engine.preview = Buffer.from([0xff, 0xd8, 0xff, 0xd9]);
  const res2 = await fetch(`${base}/api/preview.jpg`);
  assert.equal(res2.status, 200);
  assert.equal(res2.headers.get('content-type'), 'image/jpeg');
  engine.preview = null;
});

test('static files: the UI is served, unknown paths are 404, traversal is refused', async () => {
  const index = await fetch(`${base}/`);
  assert.equal(index.status, 200);
  assert.match(index.headers.get('content-type'), /text\/html/);
  assert.equal((await fetch(`${base}/missing.js`)).status, 404);
  const traversal = await fetch(`${base}/..%2F..%2Fpackage.json`);
  assert.ok([403, 404].includes(traversal.status));
});

test('shared hotkeys module is served to the browser', async () => {
  const res = await fetch(`${base}/shared/hotkeys.js`);
  assert.equal(res.status, 200);
  assert.match(await res.text(), /export function bindingFromEvent/);
});

test('unsupported methods are rejected', async () => {
  const res = await fetch(`${base}/api/project`, { method: 'DELETE' });
  assert.equal(res.status, 405);
});

test('a text/plain form post (cross-site CSRF shape) is refused before any command runs', async () => {
  const res = await fetch(`${base}/api/command`, {
    method: 'POST', headers: { 'Content-Type': 'text/plain' },
    body: JSON.stringify({ type: 'record.start', args: { format: 'mp4' } }),
  });
  assert.equal(res.status, 415);
  assert.equal((await res.json()).code, 'bad-content-type');
  assert.equal(engine.recorder, null, 'no recording may have started');
});
