// Benchmarks: (1) per-frame render cost, baseline vs cached compositor;
// (2) real encoder throughput through ffmpeg (dropped frames, realtime factor).
// Heavy assets are generated into the OS temp dir, not committed.
import { Compositor } from '../src/compositor.js';
import { createCanvas } from '@napi-rs/canvas';
import { FrameEncoder } from '../src/encoder.js';
import { resolveFfmpeg } from '../src/ffmpeg.js';
import { writeFileSync, mkdtempSync, statSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { performance } from 'node:perf_hooks';

const W = 1280, H = 720, FRAMES = Number(process.env.BENCH_FRAMES ?? 300);
const dir = mkdtempSync(join(tmpdir(), 'studio-bench-'));

// A 1920x1080 photo-like PNG (noise + gradient) makes decoding cost realistic.
const big = createCanvas(1920, 1080);
const bg = big.getContext('2d');
const grad = bg.createLinearGradient(0, 0, 1920, 1080);
grad.addColorStop(0, '#2a6df4'); grad.addColorStop(1, '#f45d2a');
bg.fillStyle = grad; bg.fillRect(0, 0, 1920, 1080);
for (let i = 0; i < 20000; i++) { bg.fillStyle = `hsl(${i % 360} 70% 50% / 0.5)`; bg.fillRect(Math.random() * 1920, Math.random() * 1080, 20, 20); }
const imgPath = join(dir, 'photo.png');
writeFileSync(imgPath, big.toBuffer('image/png'));
const imgBytes = statSync(imgPath).size;

const scene = {
  id: 'bench', name: 'bench', items: [
    { id: 'p1', kind: 'image', name: 'p1', visible: true, x: 0, y: 0, w: W, h: H, path: imgPath },
    { id: 'p2', kind: 'image', name: 'p2', visible: true, x: 0, y: 0, w: 640, h: 360, path: imgPath },
    { id: 'p3', kind: 'image', name: 'p3', visible: true, x: 640, y: 360, w: 640, h: 360, path: imgPath },
    { id: 't1', kind: 'text', name: 't1', visible: true, x: 40, y: 40, w: 900, h: 120, text: 'Сцена с текстом', color: '#fff', fontSize: 64 },
    { id: 't2', kind: 'text', name: 't2', visible: true, x: 40, y: 600, w: 900, h: 80, text: 'Нижняя строка', color: '#ffd23f', fontSize: 40 },
  ],
};

/** Runs FRAMES renders and returns timing statistics in ms. */
async function measure(cache) {
  const c = new Compositor({ width: W, height: H, cache });
  if (cache) await c.prepare(scene);
  // warm-up
  for (let i = 0; i < 5; i++) await c.renderAsync(scene);
  const times = [];
  for (let i = 0; i < FRAMES; i++) {
    const t = performance.now();
    await c.renderAsync(scene);
    c.outCtx.getImageData(0, 0, W, H); // what the recorder pays to read the frame
    times.push(performance.now() - t);
  }
  times.sort((a, b) => a - b);
  const mean = times.reduce((a, b) => a + b, 0) / times.length;
  return { meanMs: mean, p50Ms: times[Math.floor(times.length / 2)], p95Ms: times[Math.floor(times.length * 0.95)], sustainableFps: 1000 / mean };
}

const results = { env: { node: process.version, platform: process.platform, cpus: (await import('node:os')).cpus().length, imageBytes: imgBytes }, frames: FRAMES };
results.baseline = await measure(false);
results.cached = await measure(true);
results.speedupMean = results.baseline.meanMs / results.cached.meanMs;

// Encoder throughput: real ffmpeg, 10 s of 1280x720@30 = 300 frames, as fast as possible.
const ffmpegPath = await resolveFfmpeg(process.env.STUDIO_FFMPEG);
if (ffmpegPath) {
  const c = new Compositor({ width: W, height: H, cache: true });
  await c.prepare(scene);
  const out = join(dir, 'enc.mp4');
  const enc = new FrameEncoder({ ffmpegPath, width: W, height: H, fps: 30, output: out, format: 'mp4' });
  enc.start();
  const t = performance.now();
  for (let i = 0; i < 300; i++) {
    c.render(scene);
    const d = c.outCtx.getImageData(0, 0, W, H).data;
    enc.writeFrame(Buffer.from(d.buffer, d.byteOffset, d.byteLength));
    // Pace like a live clock would, so backpressure reflects real behaviour.
    const due = t + ((i + 1) * 1000) / 30;
    const wait = due - performance.now();
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  }
  const stopped = await enc.stop();
  const elapsed = (performance.now() - t) / 1000;
  results.encode = { seconds: 10, wallSeconds: elapsed, framesWritten: stopped.framesWritten, framesDropped: stopped.framesDropped, outputBytes: statSync(out).size };
  unlinkSync(out);
} else {
  results.encode = 'ffmpeg not available';
}

console.log(JSON.stringify(results, null, 2));
writeFileSync(new URL('./results.json', import.meta.url), JSON.stringify(results, null, 2) + '\n');
