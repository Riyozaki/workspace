// Compares two ways of reading the composed frame for the encoder:
// getImageData (copies into a new ImageData) vs the canvas' raw pixel buffer, if the binding exposes one.
import { createCanvas } from '@napi-rs/canvas';
import { performance } from 'node:perf_hooks';
import { writeFileSync } from 'node:fs';

const W = 1280, H = 720, N = 300;
const c = createCanvas(W, H);
const g = c.getContext('2d');
g.fillStyle = '#336699'; g.fillRect(0, 0, W, H);
const hasData = typeof c.data === 'function';

function time(fn) {
  for (let i = 0; i < 10; i++) fn();
  const t = performance.now();
  let sink = 0;
  for (let i = 0; i < N; i++) sink += fn().length;
  if (sink < 0) console.log(sink);
  return (performance.now() - t) / N;
}

const getImageDataMs = time(() => Buffer.from(g.getImageData(0, 0, W, H).data.buffer));
const result = { n: N, frame: `${W}x${H}`, getImageDataMsPerFrame: +getImageDataMs.toFixed(3), canvasDataAvailable: hasData };
if (hasData) {
  const rawMs = time(() => c.data());
  const a = Buffer.from(g.getImageData(0, 0, W, H).data.buffer);
  const b = c.data();
  result.canvasDataMsPerFrame = +rawMs.toFixed(3);
  result.speedup = +(getImageDataMs / rawMs).toFixed(2);
  result.sameBytes = Buffer.compare(a, Buffer.from(b)) === 0;
}
console.log(JSON.stringify(result, null, 2));
writeFileSync(new URL('./readback-results.json', import.meta.url), JSON.stringify(result, null, 2) + '\n');
