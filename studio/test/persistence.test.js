import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadProject, saveProject } from '../src/persistence.js';
import { createDefaultProject, ModelError } from '../src/model.js';

test('loading a missing file gives a readable ModelError', async () => {
  await assert.rejects(loadProject('/no/such/project.json'), (e) => e instanceof ModelError && /не найден/.test(e.message));
});

test('loading a file that is not JSON gives a readable ModelError', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-persist-'));
  const path = join(dir, 'broken.json');
  await writeFile(path, '{ "scenes": [');
  await assert.rejects(loadProject(path), (e) => e instanceof ModelError && /не является корректным JSON/.test(e.message));
});

test('save then load round-trips and leaves no temporary files behind', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-persist-'));
  const path = join(dir, 'proj', 'p.json');
  const project = createDefaultProject();
  project.scenes[0].items.push({ id: 'x', kind: 'text', name: 'Текст', visible: true, x: 1, y: 2, w: 300, h: 100, text: 'Привет\nмир', color: '#fff', fontSize: 40 });
  await saveProject(path, project);
  const back = await loadProject(path);
  assert.deepEqual(back.scenes[0].items[0].text, 'Привет\nмир');
  assert.deepEqual(back.canvas, project.canvas);
  const leftovers = (await readdir(join(dir, 'proj'))).filter((f) => f.includes('.tmp-'));
  assert.deepEqual(leftovers, []);
});

test('a v1 project file (no visible flag, no fps) loads with defaults', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-persist-'));
  const path = join(dir, 'v1.json');
  await writeFile(path, JSON.stringify({ canvas: { width: 1280, height: 720 }, scenes: [{ id: 'a', name: 'A', items: [{ id: 'i', kind: 'color', w: 100, h: 100 }] }] }));
  const p = await loadProject(path);
  assert.equal(p.canvas.fps, 30);
  assert.equal(p.scenes[0].items[0].visible, true);
});
