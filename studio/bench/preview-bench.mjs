// Measures what the live preview costs per update: JPEG-encoding the full
// 1280x720 frame versus a 640x360 downscaled copy (the preview is shown small).
import { createCanvas } from '@napi-rs/canvas';
import { performance } from 'node:perf_hooks';

const W = 1280, H = 720, N = 100;
const src = createCanvas(W, H);
const g = src.getContext('2d');
const grad = g.createLinearGradient(0, 0, W, H);
grad.addColorStop(0, '#2a6df4'); grad.addColorStop(1, '#f45d2a');
g.fillStyle = grad; g.fillRect(0, 0, W, H);
for (let i = 0; i < 300; i++) { g.fillStyle = `hsl(${i}deg 70% 50%)`; g.fillRect((i * 37) % W, (i * 53) % H, 60, 40); }

function time(fn) {
  for (let i = 0; i < 5; i++) fn();
  const t = performance.now();
  for (let i = 0; i < N; i++) fn();
  return (performance.now() - t) / N;
}

const full = time(() => src.toBuffer('image/jpeg', 75));
const small = createCanvas(640, 360);
const sg = small.getContext('2d');
const scaled = time(() => {
  sg.drawImage(src, 0, 0, 640, 360);
  small.toBuffer('image/jpeg', 75);
});
const bytesFull = src.toBuffer('image/jpeg', 75).length;
const bytesSmall = (sg.drawImage(src, 0, 0, 640, 360), small.toBuffer('image/jpeg', 75).length);
const result = { n: N, fullFrameJpegMs: +full.toFixed(2), downscaledJpegMs: +scaled.toFixed(2), speedup: +(full / scaled).toFixed(2), bytesFull, bytesSmall };
console.log(JSON.stringify(result, null, 2));
import { writeFileSync } from 'node:fs';
writeFileSync(new URL('./preview-results.json', import.meta.url), JSON.stringify(result, null, 2) + '\n');
