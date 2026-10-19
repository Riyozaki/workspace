import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ProjectStore, createDefaultProject } from '../src/model.js';
import { Engine } from '../src/engine.js';
import { dispatch, CommandError } from '../src/actions.js';

async function setup() {
  const dir = await mkdtemp(join(tmpdir(), 'studio-test-'));
  const store = new ProjectStore(createDefaultProject());
  const engine = new Engine({ store, ffmpegPath: 'ffmpeg', outputDir: dir });
  const projectPath = join(dir, 'p.json');
  return { ctx: { store, engine, projectPath }, dir, projectPath };
}

test('unknown command and bad arguments produce CommandError with a message', async () => {
  const { ctx } = await setup();
  await assert.rejects(dispatch(ctx, 'nope'), (e) => e instanceof CommandError && /Неизвестная/.test(e.message));
  await assert.rejects(dispatch(ctx, 'source.add', { kind: 'image' }), (e) => e instanceof CommandError);
  await assert.rejects(dispatch(ctx, 'scene.switch', { index: 9 }), (e) => e instanceof CommandError);
});

test('scene switch by index and undo through commands', async () => {
  const { ctx } = await setup();
  await dispatch(ctx, 'scene.add', { name: 'B' });
  await dispatch(ctx, 'scene.switch', { index: 0 });
  assert.equal(ctx.store.project.activeSceneId, ctx.store.project.scenes[0].id);
  await dispatch(ctx, 'source.add', { kind: 'text', text: 'hi' });
  assert.equal(ctx.store.activeScene().items.length, 1);
  await dispatch(ctx, 'edit.undo');
  assert.equal(ctx.store.activeScene().items.length, 0);
});

test('project save is atomic and reloads identically', async () => {
  const { ctx, projectPath } = await setup();
  await dispatch(ctx, 'source.add', { kind: 'color', color: '#123456', name: 'Фон' });
  await dispatch(ctx, 'project.save');
  const saved = JSON.parse(await readFile(projectPath, 'utf8'));
  assert.equal(saved.scenes[0].items[0].color, '#123456');
  assert.equal(ctx.store.dirty, false);
  const fresh = new ProjectStore(createDefaultProject());
  ctx.store = fresh;
  await dispatch(ctx, 'project.load', { path: projectPath });
  assert.equal(fresh.project.scenes[0].items[0].name, 'Фон');
});

test('stream rejects non-RTMP URLs before starting anything', async () => {
  const { ctx } = await setup();
  await assert.rejects(dispatch(ctx, 'stream.start', { url: 'http://example.com' }), (e) => e.code === 'bad-url');
  assert.equal(ctx.engine.stream, null);
});

test('record.start with a missing ffmpeg fails the command with a readable message', async () => {
  const { ctx, dir } = await setup();
  ctx.engine.ffmpegPath = join(dir, 'no-such-ffmpeg');
  await assert.rejects(dispatch(ctx, 'record.start', { format: 'mp4' }), (e) => e.code === 'no-ffmpeg' && /не найден/.test(e.message));
  assert.equal(ctx.engine.recorder, null);
  await ctx.engine.shutdown();
});

test('a failing frame is reported and the clock keeps running', async () => {
  const { ctx } = await setup();
  const eng = ctx.engine;
  let calls = 0;
  const orig = eng.ensureCompositor.bind(eng);
  eng.ensureCompositor = () => {
    calls += 1;
    if (calls === 1) throw new Error('boom');
    return orig();
  };
  eng.start();
  await new Promise((r) => setTimeout(r, 200));
  eng.ensureCompositor = orig;
  await new Promise((r) => setTimeout(r, 200));
  await eng.shutdown();
  assert.match(eng.lastError ?? '', /boom/);
  assert.ok(eng.stats.frames > 0, 'frames continued after the error');
});

test('stopping something that is not running is an explicit error', async () => {
  const { ctx } = await setup();
  await assert.rejects(dispatch(ctx, 'record.stop'), (e) => e.code === 'not-recording');
  await assert.rejects(dispatch(ctx, 'stream.stop'), (e) => e.code === 'not-streaming');
});

test('project.set-canvas changes resolution and fps and the compositor follows', async () => {
  const { ctx } = await setup();
  await dispatch(ctx, 'project.set-canvas', { width: 640, height: 360, fps: 15 });
  assert.deepEqual(ctx.store.project.canvas, { width: 640, height: 360, fps: 15 });
  assert.equal(ctx.engine.ensureCompositor().width, 640);
  await assert.rejects(dispatch(ctx, 'project.set-canvas', { width: 641, height: 360 }), (e) => e.code === 'bad-size');
  await ctx.engine.shutdown();
});

test('status reports whether ffmpeg is available so the UI can disable record/stream', async () => {
  const { ctx } = await setup();
  ctx.engine.ffmpegAvailable = false;
  const st = (await dispatch(ctx, 'status')).status;
  assert.equal(st.ffmpeg.available, false);
  await ctx.engine.shutdown();
});

test('record.start rejects an unknown container format before touching ffmpeg', async () => {
  const { ctx } = await setup();
  await assert.rejects(dispatch(ctx, 'record.start', { format: 'avi' }), (e) => e.code === 'bad-format');
  assert.equal(ctx.engine.recorder, null);
  await ctx.engine.shutdown();
});

test('adding an image or video that does not exist fails at once with a readable message', async () => {
  const { ctx } = await setup();
  await assert.rejects(dispatch(ctx, 'source.add', { kind: 'image', path: '/no/such/logo.png' }), (e) => e.code === 'file-not-found' && /не найден/.test(e.message));
  await assert.rejects(dispatch(ctx, 'source.add', { kind: 'video', path: '/no/such/clip.mp4' }), (e) => e.code === 'file-not-found');
  assert.equal(ctx.store.activeScene().items.length, 0, 'nothing may be added');
  await ctx.engine.shutdown();
});

test('model validation errors carry the code "invalid"', async () => {
  const { ctx } = await setup();
  const id = ctx.store.addSource(ctx.store.activeScene().id, { kind: 'color' });
  await assert.rejects(dispatch(ctx, 'source.update', { sceneId: ctx.store.activeScene().id, sourceId: id, patch: { w: '' } }), (e) => e.code === 'invalid');
  await ctx.engine.shutdown();
});
