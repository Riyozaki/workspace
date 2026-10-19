// Real ffmpeg runs for every container the recorder/stream path can produce.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { resolveFfmpeg } from '../src/ffmpeg.js';
import { FrameEncoder } from '../src/encoder.js';

const ffmpeg = await resolveFfmpeg(process.env.STUDIO_FFMPEG);
const skip = ffmpeg ? false : 'ffmpeg not available';

/** Encodes 15 frames of a moving gradient and returns the output path and counts. */
async function encode(format, output) {
  const enc = new FrameEncoder({ ffmpegPath: ffmpeg, width: 320, height: 180, fps: 30, output, format });
  enc.start();
  const buf = Buffer.alloc(320 * 180 * 4);
  for (let f = 0; f < 15; f++) {
    for (let i = 0; i < buf.length; i += 4) { buf[i] = f * 10; buf[i + 1] = (i >> 2) % 256; buf[i + 2] = 128; buf[i + 3] = 255; }
    await enc.waitForCapacity();
    enc.writeFrame(Buffer.from(buf));
  }
  return enc.stop();
}

/** @returns {{ codec: string, frames: number }} parsed via ffprobe-like ffmpeg -i output. */
function probe(file) {
  const r = spawnSync(ffmpeg, ['-hide_banner', '-i', file, '-map', '0:v:0', '-f', 'null', '-'], { encoding: 'utf8' });
  const codec = /Video: (\w+)/.exec(r.stderr)?.[1] ?? 'unknown';
  const frames = Number(/frame=\s*(\d+)/.exec(r.stderr)?.[1] ?? 0);
  return { codec, frames };
}

test('webm (VP9) recording is finalised and decodable', { skip }, async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const out = join(dir, 'a.webm');
  const res = await encode('webm', out);
  assert.equal(res.framesWritten, 15);
  assert.equal(res.framesDropped, 0);
  assert.ok((await stat(out)).size > 0);
  const p = probe(out);
  assert.equal(p.codec, 'vp9');
  assert.equal(p.frames, 15);
});

test('mp4 (H.264) recording reports 15 frames and decodes back to 15', { skip }, async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const out = join(dir, 'b.mp4');
  const res = await encode('mp4', out);
  assert.equal(res.framesWritten, 15);
  const p = probe(out);
  assert.equal(p.codec, 'h264');
  assert.equal(p.frames, 15);
});

test('flv output (the RTMP container) is produced with H.264 video', { skip }, async () => {
  // Local file used as a stand-in for an RTMP URL: same muxer and codec arguments.
  // A live RTMP server is not available in this sandbox, so the network leg is NOT tested.
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const out = join(dir, 'c.flv');
  const res = await encode('flv', out);
  assert.equal(res.framesWritten, 15);
  assert.equal(probe(out).codec, 'h264');
});

test('a failing encoder reports its exit code instead of hanging', { skip }, async () => {
  // The output path is an existing directory, so ffmpeg cannot write to it.
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const enc = new FrameEncoder({ ffmpegPath: ffmpeg, width: 320, height: 180, fps: 30, output: dir, format: 'mp4' });
  enc.start();
  await enc.waitForCapacity();
  enc.writeFrame(Buffer.alloc(320 * 180 * 4));
  await assert.rejects(enc.stop(), (e) => e.code === 'exit' && e.message.includes('код'));
});

test('an unusable output folder gives a readable error code', { skip }, async () => {
  // A regular file is used as the parent folder, so mkdir fails with ENOTDIR.
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const blocker = join(dir, 'blocker');
  await writeFile(blocker, 'x');
  const enc = new FrameEncoder({ ffmpegPath: ffmpeg, width: 320, height: 180, fps: 30, output: join(blocker, 'out.mp4'), format: 'mp4' });
  assert.throws(() => enc.start(), (e) => e.code === 'output-dir');
});

test('a burst that exceeds the queue is dropped and counted, not buffered forever', { skip }, async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const enc = new FrameEncoder({ ffmpegPath: ffmpeg, width: 320, height: 180, fps: 30, output: join(dir, 'burst.mp4'), format: 'mp4' });
  enc.start();
  const frame = Buffer.alloc(320 * 180 * 4);
  for (let i = 0; i < 40; i++) enc.writeFrame(frame); // no pacing: a live clock that fell behind
  const res = await enc.stop();
  assert.ok(res.framesDropped > 0, 'expected drops under a burst');
  assert.equal(res.framesWritten + res.framesDropped, 40);
});

test('mkv (H.264) recording is finalised and decodable', { skip }, async () => {
  const dir = await mkdtemp(join(tmpdir(), 'studio-rec-'));
  const out = join(dir, 'd.mkv');
  const res = await encode('mkv', out);
  assert.equal(res.framesWritten, 15);
  const p = probe(out);
  assert.equal(p.codec, 'h264');
  assert.equal(p.frames, 15);
});
