// @ts-check
import { spawn } from 'node:child_process';
import { access } from 'node:fs/promises';

/**
 * Decodes a video file (looping) into RGBA frames sized to a source's box.
 * One ffmpeg process per media source; only the newest frame is kept, so a slow
 * consumer never builds up a backlog.
 */
export class VideoDecoder {
  /**
   * @param {{ ffmpegPath: string, path: string, width: number, height: number, fps: number }} opts
   */
  constructor({ ffmpegPath, path, width, height, fps }) {
    this.ffmpegPath = ffmpegPath;
    this.path = path;
    this.width = width;
    this.height = height;
    this.fps = fps;
    this.frameSize = width * height * 4;
    /** @type {Buffer|null} */
    this.latest = null;
    /** Increments whenever a new frame arrives, so callers can skip redundant uploads. */
    this.seq = 0;
    /** @type {string|null} */
    this.error = null;
    this.proc = /** @type {import('node:child_process').ChildProcess|null} */ (null);
    this.pending = Buffer.alloc(0);
    this.stderrTail = [];
    this.stopped = false;
  }

  /** Checks the file and starts decoding. Errors are stored in `error`, not thrown. */
  async start() {
    try {
      await access(this.path);
    } catch {
      this.error = `Видеофайл не найден: ${this.path}`;
      return;
    }
    const args = [
      '-hide_banner', '-loglevel', 'error', '-nostdin',
      '-stream_loop', '-1', '-re', '-i', this.path,
      '-an', '-vf', `scale=${this.width}:${this.height}:force_original_aspect_ratio=decrease,pad=${this.width}:${this.height}:(ow-iw)/2:(oh-ih)/2,fps=${this.fps}`,
      '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1',
    ];
    const proc = spawn(this.ffmpegPath, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    this.proc = proc;
    proc.stdout.on('data', (chunk) => this.onData(chunk));
    proc.stderr.on('data', (chunk) => {
      for (const line of String(chunk).split('\n')) if (line.trim()) this.stderrTail.push(line.trim());
      if (this.stderrTail.length > 10) this.stderrTail.splice(0, this.stderrTail.length - 10);
    });
    proc.on('error', (err) => { this.error = `Не удалось запустить декодер: ${err.message}`; });
    proc.on('close', (code) => {
      if (!this.stopped && code !== 0) {
        this.error = `Декодер видео остановился (код ${code}). ${this.stderrTail.slice(-2).join(' ')}`;
      }
    });
  }

  /** @param {Buffer} chunk */
  onData(chunk) {
    this.pending = this.pending.length ? Buffer.concat([this.pending, chunk]) : chunk;
    while (this.pending.length >= this.frameSize) {
      // Copy the frame out: `pending` may be reused by the next chunk concat.
      this.latest = Buffer.from(this.pending.subarray(0, this.frameSize));
      this.pending = this.pending.subarray(this.frameSize);
      this.seq += 1;
    }
  }

  stop() {
    this.stopped = true;
    if (this.proc) this.proc.kill('SIGKILL');
  }
}
