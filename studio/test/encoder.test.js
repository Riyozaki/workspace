import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildFfmpegArgs } from '../src/encoder.js';

const base = { width: 1280, height: 720, fps: 30, output: '/tmp/x.mp4', format: 'mp4' };

test('mp4 uses H.264 yuv420p with faststart and reads raw RGBA from stdin', () => {
  const a = buildFfmpegArgs(base);
  assert.ok(a.includes('rawvideo') && a.includes('rgba') && a.includes('1280x720') && a.includes('pipe:0'));
  assert.equal(a[a.indexOf('-c:v') + 1], 'libx264');
  assert.ok(a.includes('+faststart'));
  assert.equal(a.at(-1), '/tmp/x.mp4');
});

test('webm switches to VP9 realtime', () => {
  const a = buildFfmpegArgs({ ...base, format: 'webm', output: '/tmp/x.webm' });
  assert.equal(a[a.indexOf('-c:v') + 1], 'libvpx-vp9');
  assert.ok(a.includes('realtime'));
});

test('RTMP output uses flv with bitrate and keyframe interval of 2 seconds', () => {
  const a = buildFfmpegArgs({ ...base, format: 'flv', output: 'rtmp://h/app/k', bitrateKbps: 3000 });
  assert.equal(a[a.indexOf('-f', a.length - 4) + 1], 'flv');
  assert.equal(a[a.indexOf('-b:v') + 1], '3000k');
  assert.equal(a[a.indexOf('-g') + 1], '60');
});

test('odd dimensions fail early with a clear error code', () => {
  assert.throws(() => buildFfmpegArgs({ ...base, width: 1281 }), (e) => e.code === 'bad-size');
});
