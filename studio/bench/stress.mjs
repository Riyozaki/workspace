// Sustained-load check: records SECONDS of a live scene (video source + image + text)
// through the real frame clock and ffmpeg, then reports late frames and encoder drops.
// Usage: STUDIO_FFMPEG=... STRESS_VIDEO=/path/clip.mp4 node bench/stress.mjs
import { ProjectStore, validateProject } from '../src/model.js';
import { loadProject } from '../src/persistence.js';
import { Engine } from '../src/engine.js';
import { resolveFfmpeg } from '../src/ffmpeg.js';
import { mkdtempSync, writeFileSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SECONDS = Number(process.env.STRESS_SECONDS ?? 30);
const video = process.env.STRESS_VIDEO;
if (!video) throw new Error('Set STRESS_VIDEO to a video file');
const ffmpegPath = await resolveFfmpeg(process.env.STUDIO_FFMPEG);
if (!ffmpegPath) throw new Error('ffmpeg not found');

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const base = await loadProject(join(root, 'projects', 'demo.json'));
base.scenes[0].items.push({ id: 'vid', kind: 'video', name: 'Видео', visible: true, x: 0, y: 360, w: 640, h: 360, path: video });
const store = new ProjectStore(validateProject(base));
const outDir = mkdtempSync(join(tmpdir(), 'studio-stress-'));
const engine = new Engine({ store, ffmpegPath, outputDir: outDir });
engine.start();
await engine.prepareActiveScene();
await new Promise((r) => setTimeout(r, 1000)); // let the decoder fill
const t0 = performance.now();
await engine.startRecording('mp4');
const samples = [];
while (performance.now() - t0 < SECONDS * 1000) {
  await new Promise((r) => setTimeout(r, 5000));
  samples.push({ t: Math.round((performance.now() - t0) / 1000), ...engine.status() });
}
const res = await engine.stopRecording();
const wall = (performance.now() - t0) / 1000;
await engine.shutdown();
const out = {
  seconds: SECONDS,
  wallSeconds: +wall.toFixed(2),
  framesWritten: res.framesWritten,
  framesDroppedByEncoder: res.framesDropped,
  expectedFrames: Math.round(wall * 30),
  lateFramesByClock: engine.stats.late,
  framesRendered: engine.stats.frames,
  renderMsAvg: +(engine.stats.renderMsTotal / engine.stats.frames).toFixed(2),
  lastError: engine.lastError,
  fpsSamples: samples.map((s) => s.fps),
  fileBytes: statSync(res.output).size,
};
console.log(JSON.stringify(out, null, 2));
writeFileSync(new URL('./stress-results.json', import.meta.url), JSON.stringify(out, null, 2) + '\n');
