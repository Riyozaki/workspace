// Scene transitions: a fade blends the previous frame into the new one; "cut" switches at once.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tmpdir } from 'node:os';
import { ProjectStore, createDefaultProject } from '../src/model.js';
import { Engine } from '../src/engine.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const colour = (id, color) => ({ id, name: id, items: [{ id: id + '-fill', kind: 'color', name: 'fill', x: 0, y: 0, w: 64, h: 36, color, visible: true, crop: { left: 0, top: 0, right: 0, bottom: 0 }, rotation: 0, opacity: 100 }] });

function setup(type, durationMs) {
  const project = createDefaultProject();
  project.canvas = { ...project.canvas, width: 64, height: 36, fps: 30 };
  project.scenes = [colour('a', '#ff0000'), colour('b', '#00ff00')];
  project.activeSceneId = 'a';
  project.transition = { type, durationMs };
  const store = new ProjectStore(project);
  const engine = new Engine({ store, ffmpegPath: null, outputDir: tmpdir() });
  const px = () => [...engine.ensureCompositor().out.getContext('2d').getImageData(32, 18, 1, 1).data].slice(0, 3);
  return { store, engine, px };
}

test('fade: the frame after a scene change is a blend that moves from the old scene to the new one', async (t) => {
  const { store, engine, px } = setup('fade', 300);
  t.after(() => engine.shutdown());
  await engine.tick(performance.now());
  assert.deepEqual(px(), [255, 0, 0]);

  store.setActiveScene('b');
  await engine.tick(performance.now());
  assert.ok(px()[0] > 200 && px()[1] < 60, `start of fade is still mostly red: ${px()}`);

  await sleep(150);
  await engine.tick(performance.now());
  const [r, g] = px();
  assert.ok(r > 40 && r < 215 && g > 40 && g < 215, `mid-fade pixel must be a mix: ${px()}`);

  await sleep(300);
  await engine.tick(performance.now());
  assert.deepEqual(px(), [0, 255, 0], 'after the duration the new scene is shown unblended');
  assert.equal(engine.transition, null);
});

test('cut: the scene changes on the next frame with no blend', async (t) => {
  const { store, engine, px } = setup('cut', 300);
  t.after(() => engine.shutdown());
  await engine.tick(performance.now());
  store.setActiveScene('b');
  await engine.tick(performance.now());
  assert.deepEqual(px(), [0, 255, 0]);
  assert.equal(engine.transition, null);
});

test('transition settings are validated: unknown type becomes fade, duration is bounded', async () => {
  const { validateProject, createDefaultProject: make } = await import('../src/model.js');
  const project = make();
  project.transition = { type: 'swipe', durationMs: 99999 };
  assert.deepEqual(validateProject(project).transition, { type: 'fade', durationMs: 5000 });
});
