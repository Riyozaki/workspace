import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ProjectStore, createDefaultProject, validateProject, ModelError, MAX_SOURCES_PER_SCENE } from '../src/model.js';

test('validateProject clamps canvas and rejects empty scenes', () => {
  const p = validateProject({ canvas: { width: 99999, height: 1, fps: 0 }, scenes: [{ id: 'a', items: [] }] });
  assert.deepEqual(p.canvas, { width: 7680, height: 16, fps: 1 });
  assert.throws(() => validateProject({ scenes: [] }), ModelError);
  assert.throws(() => validateProject(null), ModelError);
});

test('validateProject migrates v1 sources (no visible flag) and unknown kinds', () => {
  const p = validateProject({ scenes: [{ id: 's', items: [{ id: 'x', kind: 'weird', w: 0 }] }] });
  const it = p.scenes[0].items[0];
  assert.equal(it.kind, 'color');
  assert.equal(it.visible, true);
  assert.equal(it.w, 320);
});

test('duplicate scene ids are rejected', () => {
  assert.throws(() => validateProject({ scenes: [{ id: 'a', items: [] }, { id: 'a', items: [] }] }), /одинаковым id/);
});

test('undo/redo restores exact previous state', () => {
  const store = new ProjectStore(createDefaultProject());
  const sid = store.project.scenes[0].id;
  store.addSource(sid, { kind: 'color', name: 'A' });
  store.addSource(sid, { kind: 'color', name: 'B' });
  assert.equal(store.project.scenes[0].items.length, 2);
  assert.ok(store.undo());
  assert.equal(store.project.scenes[0].items.length, 1);
  assert.ok(store.redo());
  assert.equal(store.project.scenes[0].items.length, 2);
  assert.equal(store.redo(), false);
});

test('scene switching is not an undoable edit', () => {
  const store = new ProjectStore(createDefaultProject());
  store.addScene('Two');
  const before = store.undoStack.length;
  store.setActiveScene(store.project.scenes[0].id);
  assert.equal(store.undoStack.length, before);
});

test('updateSource clamps geometry so the source stays reachable', () => {
  const store = new ProjectStore(createDefaultProject());
  const sid = store.project.scenes[0].id;
  const id = store.addSource(sid, { kind: 'color' });
  store.updateSource(sid, id, { x: -100000, y: 100000, w: 5000, h: -4 });
  const it = store.project.scenes[0].items[0];
  assert.equal(it.w, 1280);
  assert.equal(it.h, 1);
  assert.ok(it.x >= -it.w + 1);
  assert.ok(it.y <= 719);
});

test('moveSource changes z-order and ignores moves past the ends', () => {
  const store = new ProjectStore(createDefaultProject());
  const sid = store.project.scenes[0].id;
  const a = store.addSource(sid, { kind: 'color', name: 'a' });
  const b = store.addSource(sid, { kind: 'color', name: 'b' });
  store.moveSource(sid, a, 1);
  assert.deepEqual(store.project.scenes[0].items.map((i) => i.id), [b, a]);
  store.moveSource(sid, a, 1); // already on top: no-op
  assert.deepEqual(store.project.scenes[0].items.map((i) => i.id), [b, a]);
});

test('source limit per scene is enforced', () => {
  const store = new ProjectStore(createDefaultProject());
  const sid = store.project.scenes[0].id;
  for (let i = 0; i < MAX_SOURCES_PER_SCENE; i++) store.addSource(sid, { kind: 'color' });
  assert.throws(() => store.addSource(sid, { kind: 'color' }), /лимит/);
});

test('cannot remove the last scene', () => {
  const store = new ProjectStore(createDefaultProject());
  assert.throws(() => store.removeScene(store.project.scenes[0].id), /последнюю/);
});
