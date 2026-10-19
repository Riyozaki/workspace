// Pixel-level tests for crop, rotation and opacity, and validation of the new fields.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createCanvas } from '@napi-rs/canvas';
import { Compositor } from '../src/compositor.js';
import { ProjectStore, createDefaultProject, validateProject, ModelError } from '../src/model.js';

const px = (c, x, y) => [...c.outCtx.getImageData(x, y, 1, 1).data];

function scene(items) {
  return { id: 's', name: 's', items: items.map((it) => ({ visible: true, crop: { left: 0, top: 0, right: 0, bottom: 0 }, rotation: 0, opacity: 100, ...it })) };
}

test('crop removes pixels before scaling: the left half of the source is cut away', async () => {
  // Source image: left half red, right half blue.
  const img = createCanvas(100, 50);
  const g = img.getContext('2d');
  g.fillStyle = '#ff0000'; g.fillRect(0, 0, 50, 50);
  g.fillStyle = '#0000ff'; g.fillRect(50, 0, 50, 50);
  const dir = await mkdtemp(join(tmpdir(), 'studio-crop-'));
  const path = join(dir, 'split.png');
  await writeFile(path, img.toBuffer('image/png'));

  const c = new Compositor({ width: 100, height: 100 });
  const s = scene([{ id: 'i', kind: 'image', name: 'i', x: 0, y: 0, w: 50, h: 50, path, crop: { left: 50, top: 0, right: 0, bottom: 0 } }]);
  await c.prepare(s);
  c.render(s);
  assert.deepEqual(px(c, 25, 25), [0, 0, 255, 255], 'with the red half cropped away only blue remains');
});

test('rotation turns the box around its centre', () => {
  const c = new Compositor({ width: 100, height: 100 });
  // A horizontal red bar 40x10 centred at (40,25).
  const s = scene([{ id: 'r', kind: 'color', name: 'r', x: 20, y: 20, w: 40, h: 10, color: '#ff0000', rotation: 90 }]);
  c.render(s);
  assert.deepEqual(px(c, 40, 40), [255, 0, 0, 255], 'lower part of the rotated (vertical) bar is red');
  assert.deepEqual(px(c, 25, 25), [0, 0, 0, 255], 'the original horizontal position is now empty');
});

test('opacity blends the source with what is underneath', () => {
  const c = new Compositor({ width: 20, height: 20 });
  const s = scene([{ id: 'r', kind: 'color', name: 'r', x: 0, y: 0, w: 20, h: 20, color: '#ff0000', opacity: 50 }]);
  c.render(s);
  const [r, g, b] = px(c, 10, 10);
  assert.ok(r >= 120 && r <= 136, `red channel ${r}`);
  assert.equal(g, 0);
  assert.equal(b, 0);
});

test('a state after a transformed source does not leak into the next one (save/restore)', () => {
  const c = new Compositor({ width: 40, height: 40 });
  const s = scene([
    { id: 'a', kind: 'color', name: 'a', x: 0, y: 0, w: 40, h: 40, color: '#00ff00', opacity: 0 },
    { id: 'b', kind: 'color', name: 'b', x: 0, y: 0, w: 40, h: 40, color: '#0000ff' },
  ]);
  c.render(s);
  assert.deepEqual(px(c, 5, 5), [0, 0, 255, 255], 'the second source must be drawn at full opacity');
});

test('model normalises rotation and clamps opacity; invalid transform values are rejected', () => {
  const p = validateProject({ scenes: [{ id: 's', items: [{ id: 'x', kind: 'color', rotation: 450, opacity: 200, crop: { left: -5, top: 3 } }] }] });
  const it = p.scenes[0].items[0];
  assert.equal(it.rotation, 90);
  assert.equal(it.opacity, 100);
  assert.deepEqual(it.crop, { left: 0, top: 3, right: 0, bottom: 0 });

  const store = new ProjectStore(createDefaultProject());
  const sid = store.project.scenes[0].id;
  const id = store.addSource(sid, { kind: 'color' });
  assert.throws(() => store.updateSource(sid, id, { opacity: 150 }), (e) => e instanceof ModelError && /0 до 100/.test(e.message));
  assert.throws(() => store.updateSource(sid, id, { crop: { left: -1, top: 0, right: 0, bottom: 0 } }), ModelError);
  store.updateSource(sid, id, { opacity: 25, rotation: 45, crop: { left: 4, top: 0, right: 0, bottom: 0 } });
  assert.equal(store.project.scenes[0].items[0].opacity, 25);
});
