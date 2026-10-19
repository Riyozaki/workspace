import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Compositor } from '../src/compositor.js';
import { loadProject } from '../src/persistence.js';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Returns [r,g,b,a] at (x,y) of the compositor output. */
function pixel(comp, x, y) {
  const d = comp.outCtx.getImageData(x, y, 1, 1).data;
  return [d[0], d[1], d[2], d[3]];
}

test('colour source fills its rectangle and only that rectangle', () => {
  const c = new Compositor({ width: 100, height: 100 });
  const scene = { id: 's', name: 's', items: [{ id: 'a', kind: 'color', name: 'a', visible: true, x: 10, y: 10, w: 20, h: 20, color: '#ff0000' }] };
  c.render(scene);
  assert.deepEqual(pixel(c, 15, 15), [255, 0, 0, 255]);
  assert.deepEqual(pixel(c, 5, 5), [0, 0, 0, 255]);
});

test('hidden sources are not drawn', () => {
  const c = new Compositor({ width: 50, height: 50 });
  const scene = { id: 's', name: 's', items: [{ id: 'a', kind: 'color', name: 'a', visible: false, x: 0, y: 0, w: 50, h: 50, color: '#fff' }] };
  c.render(scene);
  assert.deepEqual(pixel(c, 25, 25), [0, 0, 0, 255]);
});

test('later items are drawn on top (z-order)', () => {
  const c = new Compositor({ width: 50, height: 50 });
  const base = { kind: 'color', visible: true, x: 0, y: 0, w: 50, h: 50 };
  c.render({ id: 's', name: 's', items: [{ ...base, id: 'a', name: 'a', color: '#ff0000' }, { ...base, id: 'b', name: 'b', color: '#00ff00' }] });
  assert.deepEqual(pixel(c, 25, 25), [0, 255, 0, 255]);
});

test('cached and baseline renderers produce identical pixels for the demo scene', async () => {
  const project = await loadProject(join(root, 'projects', 'demo.json'));
  const scene = project.scenes[0];
  const cached = new Compositor({ width: 1280, height: 720, cache: true });
  await cached.prepare(scene);
  cached.render(scene);
  const baseline = new Compositor({ width: 1280, height: 720, cache: false });
  await baseline.renderAsync(scene);
  const a = cached.outCtx.getImageData(0, 0, 1280, 720).data;
  const b = baseline.outCtx.getImageData(0, 0, 1280, 720).data;
  assert.equal(a.length, b.length);
  let diff = 0;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) diff++;
  assert.equal(diff, 0, `renderers differ in ${diff} channel values`);
});

test('missing image becomes a warning, not a crash', async () => {
  const c = new Compositor({ width: 40, height: 40 });
  const scene = { id: 's', name: 's', items: [{ id: 'i', kind: 'image', name: 'Нет', visible: true, x: 0, y: 0, w: 40, h: 40, path: '/no/such/file.png' }] };
  await c.prepare(scene);
  assert.equal(c.warnings.length, 1);
  assert.match(c.warnings[0], /Нет/);
  c.render(scene); // must not throw
});
