// Engine tests with the real ffmpeg binary (skipped when it is unavailable).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ProjectStore, createDefaultProject } from '../src/model.js';
import { Engine } from '../src/engine.js';
import { resolveFfmpeg } from '../src/ffmpeg.js';

const ffmpeg = await resolveFfmpeg(process.env.STUDIO_FFMPEG);
const skip = ffmpeg ? false : 'ffmpeg not available';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function makeEngine(canvas = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'studio-engine-'));
  const project = createDefaultProject();
  project.canvas = { ...project.canvas, width: 320, height: 180, fps: 30, ...canvas };
  const store = new ProjectStore(project);
  const engine = new Engine({ store, ffmpegPath: ffmpeg, outputDir: dir });
  return { engine, store, dir };
}

test('recording through the frame clock writes a playable file and counts frames', { skip }, async (t) => {
  const { engine, dir } = await makeEngine();
  t.after(() => engine.shutdown());
  const output = await engine.startRecording('mp4');
  await sleep(1000);
  const res = await engine.stopRecording();
  assert.equal(res.output, output);
  assert.ok(res.framesWritten >= 20 && res.framesWritten <= 36, `frames written: ${res.framesWritten}`);
  assert.ok((await readdir(dir)).some((f) => f.endsWith('.mp4')));
  assert.ok(engine.stats.frames > 0);
});

test('a second recording while one runs is refused', { skip }, async (t) => {
  const { engine } = await makeEngine();
  t.after(() => engine.shutdown());
  await engine.startRecording('mp4');
  await assert.rejects(engine.startRecording('mp4'), (e) => e.code === 'busy');
  await engine.stopRecording();
});

test('RTMP to a closed port fails with a message in status, and the clock keeps running', { skip }, async (t) => {
  const { engine } = await makeEngine();
  t.after(() => engine.shutdown());
  await engine.startStream('rtmp://127.0.0.1:1/live/test', 500);
  // ffmpeg fails to connect quickly; the error must surface, not hang.
  for (let i = 0; i < 100 && !engine.lastError; i++) await sleep(100);
  assert.ok(engine.lastError, 'expected a connection error');
  assert.ok(engine.running, 'frame clock must keep running for the preview');
  assert.equal(engine.stream, null);
});

test('recording a scene with a colour source produces the right colour in frames', { skip }, async (t) => {
  const { engine, store } = await makeEngine();
  t.after(() => engine.shutdown());
  const sid = store.activeScene().id;
  store.addSource(sid, { kind: 'color', color: '#00ff00', x: 0, y: 0, w: 320, h: 180 });
  await engine.prepareActiveScene();
  engine.start();
  await sleep(150);
  const rgba = engine.readRgba(engine.ensureCompositor());
  assert.deepEqual([rgba[0], rgba[1], rgba[2]], [0, 255, 0]);
});

test('status exposes fps and frame timing after running', { skip }, async (t) => {
  const { engine } = await makeEngine();
  t.after(() => engine.shutdown());
  engine.start();
  await sleep(1100);
  const st = engine.status();
  assert.ok(st.fps > 10, `fps ${st.fps}`);
  assert.ok(st.renderMsAvg >= 0);
});

test('a missing ffmpeg is reported immediately to the caller, not later through status', { skip: false }, async () => {
  const { engine } = await makeEngine();
  engine.ffmpegPath = '/definitely/not/here/ffmpeg';
  await assert.rejects(engine.startRecording('mp4'), (e) => e.code === 'no-ffmpeg' && /не найден/.test(e.message));
  assert.equal(engine.recorder, null, 'no half-started recorder may remain');
  await engine.shutdown();
});

test('preview is a JPEG downscaled to at most 640 px wide and keeps the aspect ratio', async (t) => {
  const { engine } = await makeEngine({ width: 1280, height: 720 });
  t.after(() => engine.shutdown());
  const comp = engine.ensureCompositor();
  comp.render(engine.store.activeScene());
  const { loadImage } = await import('@napi-rs/canvas');
  const img = await loadImage(engine.encodePreview(comp));
  assert.equal(img.width, 640);
  assert.equal(img.height, 360);
});

test('switching scenes while running keeps frames flowing and prepares the new scene', async (t) => {
  const { engine, store } = await makeEngine();
  t.after(() => engine.shutdown());
  const first = store.activeScene().id;
  const second = store.addScene('Вторая');
  store.addSource(second, { kind: 'color', color: '#ff0000', x: 0, y: 0, w: 320, h: 180 });
  engine.start();
  await sleep(120);
  const before = engine.stats.frames;
  store.setActiveScene(second);
  for (let i = 0; i < 50 && engine.preparedSceneId !== second; i++) await sleep(20);
  assert.equal(engine.preparedSceneId, second, 'new scene was not prepared');
  await sleep(120);
  assert.ok(engine.stats.frames > before + 2, 'frames stopped after the switch');
  const px = engine.readRgba(engine.ensureCompositor());
  assert.deepEqual([px[0], px[1], px[2]], [255, 0, 0], 'frame does not show the new scene');
  store.setActiveScene(first);
});
