// Integration tests that run the real ffmpeg binary. Skipped when ffmpeg is unavailable.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { resolveFfmpeg } from '../src/ffmpeg.js';
import { FrameEncoder } from '../src/encoder.js';
import { VideoDecoder } from '../src/media.js';
import { Compositor } from '../src/compositor.js';
import { createCanvas } from '@napi-rs/canvas';

const ffmpeg = await resolveFfmpeg(process.env.STUDIO_FFMPEG);
const skip = ffmpeg ? false : 'ffmpeg not available';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Writes a 1-second solid-green mp4 (320x180, 30 fps) and returns its path. */
async function makeClip() {
  const dir = await mkdtemp(join(tmpdir(), 'studio-media-'));
  const out = join(dir, 'green.mp4');
  const enc = new FrameEncoder({ ffmpegPath: ffmpeg, width: 320, height: 180, fps: 30, output: out, format: 'mp4' });
  enc.start();
  const buf = Buffer.alloc(320 * 180 * 4);
  for (let i = 0; i < 30; i++) {
    for (let p = 0; p < buf.length; p += 4) { buf[p] = 0; buf[p + 1] = 255; buf[p + 2] = 0; buf[p + 3] = 255; }
    enc.writeFrame(Buffer.from(buf));
  }
  await enc.stop();
  return out;
}

test('decoder returns frames whose colour matches the encoded clip', { skip }, async () => {
  const path = await makeClip();
  const dec = new VideoDecoder({ ffmpegPath: ffmpeg, path, width: 160, height: 90, fps: 30 });
  await dec.start();
  for (let i = 0; i < 50 && !dec.latest; i++) await sleep(50);
  assert.ok(dec.latest, 'no frame decoded');
  assert.equal(dec.latest.length, 160 * 90 * 4);
  const mid = (45 * 160 + 80) * 4; // centre pixel
  assert.ok(dec.latest[mid + 1] > 200 && dec.latest[mid] < 60, `expected green, got ${[...dec.latest.subarray(mid, mid + 4)]}`);
  dec.stop();
});

test('missing media file is reported as an error, not a crash', { skip }, async () => {
  const dec = new VideoDecoder({ ffmpegPath: ffmpeg, path: '/no/such/clip.mp4', width: 16, height: 16, fps: 30 });
  await dec.start();
  assert.match(dec.error ?? '', /не найден/);
});

test('compositor draws the decoded frame into the video source rectangle', { skip }, async () => {
  const path = await makeClip();
  const dec = new VideoDecoder({ ffmpegPath: ffmpeg, path, width: 64, height: 36, fps: 30 });
  await dec.start();
  for (let i = 0; i < 50 && !dec.latest; i++) await sleep(50);
  const c = new Compositor({ width: 200, height: 100 });
  const canvas = createCanvas(64, 36);
  canvas.getContext('2d').putImageData(new (await import('@napi-rs/canvas')).ImageData(new Uint8ClampedArray(dec.latest), 64, 36), 0, 0);
  c.videoFrames.set('v', canvas);
  const scene = { id: 's', name: 's', items: [{ id: 'v', kind: 'video', name: 'v', visible: true, x: 100, y: 50, w: 64, h: 36, path }] };
  c.render(scene);
  const px = c.outCtx.getImageData(120, 60, 1, 1).data;
  assert.ok(px[1] > 200, `expected green in video rectangle, got ${[...px]}`);
  assert.deepEqual([...c.outCtx.getImageData(10, 10, 1, 1).data], [0, 0, 0, 255]);
  dec.stop();
});
