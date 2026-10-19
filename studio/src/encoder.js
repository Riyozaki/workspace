// @ts-check
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

/**
 * @typedef {'mp4'|'webm'|'mkv'|'flv'} ContainerFormat
 * @typedef {{ width: number, height: number, fps: number, output: string,
 *            format: ContainerFormat, bitrateKbps?: number }} EncoderConfig
 */

export class EncoderError extends Error {
  /** @param {string} message @param {{ code?: string, details?: string }} [extra] */
  constructor(message, extra = {}) {
    super(message);
    this.name = 'EncoderError';
    this.code = extra.code ?? 'encoder';
    this.details = extra.details ?? '';
  }
}

/**
 * Builds ffmpeg arguments for raw RGBA frames on stdin. Pure function: the
 * unit tests check the arguments without starting a process.
 * @param {EncoderConfig} cfg
 * @returns {string[]}
 */
export function buildFfmpegArgs(cfg) {
  const { width, height, fps, output, format } = cfg;
  if (width % 2 || height % 2) {
    // yuv420p requires even dimensions; fail early with an explanation.
    throw new EncoderError(`Размер ${width}×${height} должен быть чётным для H.264/VP9 (yuv420p).`, { code: 'bad-size' });
  }
  const br = `${cfg.bitrateKbps ?? 4000}k`;
  const args = [
    '-hide_banner', '-loglevel', 'error', '-nostdin',
    '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${width}x${height}`, '-r', String(fps), '-i', 'pipe:0',
  ];
  if (format === 'webm') {
    args.push('-c:v', 'libvpx-vp9', '-deadline', 'realtime', '-cpu-used', '8', '-b:v', br, '-pix_fmt', 'yuv420p');
  } else {
    // H.264 for mp4/mkv/flv (flv is what RTMP expects).
    args.push('-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'zerolatency', '-b:v', br,
      '-maxrate', br, '-bufsize', `${(cfg.bitrateKbps ?? 4000) * 2}k`, '-g', String(fps * 2), '-pix_fmt', 'yuv420p');
    if (format === 'mp4') args.push('-movflags', '+faststart');
  }
  // ffmpeg muxer names differ from file extensions: mkv is the 'matroska' muxer.
  const muxer = { flv: 'flv', mkv: 'matroska', mp4: 'mp4', webm: 'webm' }[format];
  args.push('-f', muxer, '-y', output);
  return args;
}

/**
 * Wraps an ffmpeg child process that consumes raw frames. Frames are written
 * with backpressure: if the encoder falls behind by more than `maxPending`
 * frames, new frames are dropped and counted, instead of growing memory.
 */
export class FrameEncoder {
  /**
   * @param {EncoderConfig & { ffmpegPath: string, maxPending?: number }} cfg
   */
  constructor(cfg) {
    this.cfg = cfg;
    this.maxPending = cfg.maxPending ?? 6;
    this.pending = 0;
    this.framesWritten = 0;
    this.framesDropped = 0;
    /** @type {string[]} */
    this.stderrTail = [];
    this.exited = false;
    /** Set by stop(); distinguishes a requested finish from a crash. */
    this.stopRequested = false;
    /** @type {import('node:child_process').ChildProcess|null} */
    this.proc = null;
    /** @type {Promise<{code:number|null}>} */
    this.done = Promise.resolve({ code: 0 });
  }

  /**
   * Starts ffmpeg. Resolves once the process has actually been spawned, and
   * rejects with an EncoderError (e.g. ffmpeg not found) so the caller can
   * answer the user immediately instead of reporting success and failing later.
   * @returns {Promise<void>}
   */
  start() {
    const { ffmpegPath, output } = this.cfg;
    // Only local file outputs need a directory; rtmp:// URLs do not.
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(output)) {
      try {
        mkdirSync(dirname(output), { recursive: true });
      } catch (err) {
        throw new EncoderError(`Не удалось создать папку для записи «${dirname(output)}»: ${/** @type {Error} */ (err).message}`, { code: 'output-dir' });
      }
    }
    const args = buildFfmpegArgs(this.cfg);
    const proc = spawn(ffmpegPath, args, { stdio: ['pipe', 'ignore', 'pipe'] });
    this.proc = proc;
    const spawnError = (/** @type {Error} */ err) => {
      const code = /** @type {NodeJS.ErrnoException} */ (err).code;
      return new EncoderError(
        code === 'ENOENT'
          ? `ffmpeg не найден по пути «${ffmpegPath}». Укажите путь переменной STUDIO_FFMPEG.`
          : `Не удалось запустить ffmpeg: ${err.message}`,
        { code: code === 'ENOENT' ? 'no-ffmpeg' : 'spawn' },
      );
    };
    this.spawned = new Promise((resolve, reject) => {
      proc.once('spawn', () => resolve(undefined));
      proc.once('error', (err) => reject(spawnError(err)));
    });
    // Handled by the caller via start()'s promise; this copy only prevents an unhandled rejection.
    this.spawned.catch(() => {});
    this.done = new Promise((resolve, reject) => {
      proc.on('error', (err) => {
        this.exited = true;
        reject(spawnError(err));
      });
      proc.stderr.on('data', (chunk) => {
        for (const line of String(chunk).split('\n')) {
          if (line.trim()) this.stderrTail.push(line.trim());
        }
        if (this.stderrTail.length > 20) this.stderrTail.splice(0, this.stderrTail.length - 20);
      });
      proc.stdin.on('error', () => { /* reported through exit code */ });
      proc.on('close', (code) => {
        this.exited = true;
        resolve({ code });
      });
      // Also settle on a crash: the 'error' event alone does not always fire.
      proc.on('exit', (code) => {
        this.exited = true;
        resolve({ code });
      });
    });
    // A spawn error must still surface through stop(); keep it from being unhandled.
    this.done.catch(() => {});
    return this.spawned;
  }

  /**
   * Writes one RGBA frame. Returns false if the frame was dropped.
   * @param {Buffer} rgba
   */
  writeFrame(rgba) {
    if (!this.proc || this.exited || !this.proc.stdin?.writable) return false;
    if (this.pending >= this.maxPending) {
      this.framesDropped += 1;
      return false;
    }
    this.pending += 1;
    this.proc.stdin?.write(rgba, (err) => {
      this.pending -= 1;
      if (err) this.framesDropped += 1;
      else this.framesWritten += 1;
    });
    return true;
  }

  /**
   * Resolves once the encoder has room for another frame. Live clocks do not
   * need this (they drop when behind); offline writers (tests, batch jobs) use it to pace.
   * @returns {Promise<void>}
   */
  async waitForCapacity() {
    while (this.pending >= this.maxPending && !this.exited) {
      await new Promise((r) => setTimeout(r, 2));
    }
  }

  /**
   * Ends the stream and waits for ffmpeg to finalise the container.
   * @returns {Promise<{ framesWritten: number, framesDropped: number }>}
   */
  async stop() {
    if (!this.proc) throw new EncoderError('Запись не была запущена.', { code: 'not-started' });
    const proc = this.proc;
    this.stopRequested = true;
    proc.stdin?.end();
    const { code } = await this.done;
    if (code !== 0) {
      throw new EncoderError(
        `ffmpeg завершился с ошибкой (код ${code}). Файл может быть повреждён.`,
        { code: 'exit', details: this.stderrTail.slice(-5).join('\n') },
      );
    }
    return { framesWritten: this.framesWritten, framesDropped: this.framesDropped };
  }

  /** Message for an unexpected exit (crash, dead RTMP server, full disk), or null. */
  failureMessage() {
    if (!this.exited || this.stopRequested) return null;
    const tail = this.stderrTail.slice(-3).join(' ');
    return `Вывод остановлен неожиданно (ffmpeg завершился). ${tail}`.trim();
  }

  /** Kill without finalising; used on shutdown. */
  kill() {
    if (this.proc && !this.exited) this.proc.kill('SIGKILL');
  }
}
