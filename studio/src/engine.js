// @ts-check
import { Compositor } from './compositor.js';
import { FrameEncoder, EncoderError } from './encoder.js';

/**
 * Output frame clock. Drives the compositor at the canvas FPS, feeds the
 * active outputs (file recorder / RTMP stream) and keeps statistics that the UI shows.
 *
 * Timing: frames are scheduled against an absolute timeline (start + n*interval)
 * rather than "now + interval", so timer jitter does not accumulate as drift.
 * A tick that starts more than one interval late counts as a dropped frame.
 */
export class Engine {
  /**
   * @param {{ store: import('./model.js').ProjectStore, ffmpegPath: string,
   *          outputDir: string, baseline?: boolean, previewFps?: number }} opts
   */
  constructor({ store, ffmpegPath, outputDir, baseline = false, previewFps = 10 }) {
    this.store = store;
    this.ffmpegPath = ffmpegPath;
    this.outputDir = outputDir;
    this.baseline = baseline;
    this.previewIntervalMs = 1000 / previewFps;
    /** @type {Compositor|null} */
    this.compositor = null;
    /** @type {FrameEncoder|null} */
    this.recorder = null;
    /** @type {FrameEncoder|null} */
    this.stream = null;
    /** @type {Buffer|null} */
    this.preview = null;
    this.previewAt = 0;
    this.running = false;
    this.timer = /** @type {NodeJS.Timeout|null} */ (null);
    this.stats = { frames: 0, late: 0, renderMsTotal: 0, renderMsLast: 0, fps: 0 };
    this.fpsWindow = { start: 0, frames: 0 };
    /** @type {string[]} */
    this.warnings = [];
    /** @type {string|null} */
    this.lastError = null;
  }

  /** Canvas-size-dependent objects are rebuilt when the canvas changes. */
  ensureCompositor() {
    const { width, height } = this.store.project.canvas;
    if (!this.compositor || this.compositor.width !== width || this.compositor.height !== height) {
      this.compositor = new Compositor({ width, height, cache: !this.baseline });
    }
    return this.compositor;
  }

  /**
   * Decodes images of the active scene before they are drawn, and drops layer
   * caches that no source uses any more. Called at startup and on scene switch.
   */
  async prepareActiveScene() {
    const scene = this.store.activeScene();
    const comp = this.ensureCompositor();
    await comp.prepare(scene);
    comp.pruneLayers(this.store.project.scenes);
    this.preparedSceneId = scene.id;
  }

  /** Starts the frame clock. Idempotent. */
  start() {
    if (this.running) return;
    this.running = true;
    this.lastError = null;
    const { fps } = this.store.project.canvas;
    this.intervalMs = 1000 / fps;
    this.t0 = performance.now();
    this.tickIndex = 0;
    this.stats = { frames: 0, late: 0, renderMsTotal: 0, renderMsLast: 0, fps: 0 };
    this.fpsWindow = { start: this.t0, frames: 0 };
    this.scheduleNext();
  }

  scheduleNext() {
    if (!this.running) return;
    const due = this.t0 + this.tickIndex * this.intervalMs;
    const wait = Math.max(0, due - performance.now());
    this.timer = setTimeout(() => {
      // A failing frame must not stop the clock: record the error and keep going.
      this.tick(due).catch((err) => {
        this.lastError = `Ошибка при отрисовке кадра: ${/** @type {Error} */ (err).message}`;
        this.stats.errors = (this.stats.errors ?? 0) + 1;
        this.scheduleNext();
      });
    }, wait);
  }

  /** @param {number} due */
  async tick(due) {
    const now = performance.now();
    if (now - due > this.intervalMs) this.stats.late += 1;
    this.tickIndex += 1;
    const scene = this.store.activeScene();
    const comp = this.ensureCompositor();
    if (this.preparedSceneId !== scene.id && !this.preparing) {
      // Scene switched: decode its images in the background; frames keep flowing.
      this.preparing = true;
      this.prepareActiveScene().finally(() => { this.preparing = false; });
    }
    const t = performance.now();
    await comp.renderAsync(scene);
    const renderMs = performance.now() - t;
    this.stats.renderMsLast = renderMs;
    this.stats.renderMsTotal += renderMs;
    this.stats.frames += 1;

    const rgba = this.recorder || this.stream ? this.readRgba(comp) : null;
    if (this.recorder && rgba) this.recorder.writeFrame(rgba);
    if (this.stream && rgba) this.stream.writeFrame(rgba);

    if (now - this.previewAt >= this.previewIntervalMs) {
      this.previewAt = now;
      this.preview = comp.encodeJpeg(75);
    }

    this.fpsWindow.frames += 1;
    if (now - this.fpsWindow.start >= 1000) {
      this.stats.fps = (this.fpsWindow.frames * 1000) / (now - this.fpsWindow.start);
      this.fpsWindow = { start: now, frames: 0 };
    }
    this.scheduleNext();
  }

  /** @param {any} comp @returns {Buffer} */
  readRgba(comp) {
    const { width, height } = comp;
    const data = comp.outCtx.getImageData(0, 0, width, height).data;
    return Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  }

  /** Stops the frame clock and all outputs (finalising files). */
  async shutdown() {
    this.running = false;
    if (this.timer) clearTimeout(this.timer);
    await this.stopRecording().catch(() => {});
    await this.stopStream().catch(() => {});
  }

  /** Starts a file recording. @param {'mp4'|'webm'|'mkv'} format */
  startRecording(format = 'mp4') {
    if (this.recorder) throw new EncoderError('Запись уже идёт.', { code: 'busy' });
    const { width, height, fps } = this.store.project.canvas;
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const output = `${this.outputDir}/recording-${stamp}.${format}`;
    this.recorder = new FrameEncoder({ ffmpegPath: this.ffmpegPath, width, height, fps, output, format });
    this.recorder.start();
    this.recorder.done.catch((err) => { this.lastError = err.message; this.recorder = null; });
    this.start();
    return output;
  }

  /** @returns {Promise<{output:string, framesWritten:number, framesDropped:number}|null>} */
  async stopRecording() {
    if (!this.recorder) return null;
    const rec = this.recorder;
    this.recorder = null;
    const res = await rec.stop();
    return { output: rec.cfg.output, ...res };
  }

  /** Starts an RTMP stream. @param {string} url rtmp://host/app/key @param {number} bitrateKbps */
  startStream(url, bitrateKbps = 3000) {
    if (this.stream) throw new EncoderError('Трансляция уже идёт.', { code: 'busy' });
    if (!/^rtmps?:\/\//.test(url)) throw new EncoderError('Адрес должен начинаться с rtmp:// или rtmps://.', { code: 'bad-url' });
    const { width, height, fps } = this.store.project.canvas;
    this.stream = new FrameEncoder({ ffmpegPath: this.ffmpegPath, width, height, fps, output: url, format: 'flv', bitrateKbps });
    this.stream.start();
    this.stream.done.catch((err) => { this.lastError = err.message; this.stream = null; });
    this.start();
  }

  /** @returns {Promise<{framesWritten:number, framesDropped:number}|null>} */
  async stopStream() {
    if (!this.stream) return null;
    const s = this.stream;
    this.stream = null;
    return s.stop();
  }

  /** Snapshot for the UI and tests. */
  status() {
    const s = this.stats;
    return {
      running: this.running,
      recording: this.recorder ? this.recorder.cfg.output : null,
      streaming: this.stream ? 'rtmp' : null,
      fps: Math.round(s.fps * 10) / 10,
      frames: s.frames,
      lateFrames: s.late,
      encoderDropped: (this.recorder?.framesDropped ?? 0) + (this.stream?.framesDropped ?? 0),
      renderMsAvg: s.frames ? Math.round((s.renderMsTotal / s.frames) * 100) / 100 : 0,
      renderMsLast: Math.round(s.renderMsLast * 100) / 100,
      lastError: this.lastError,
      warnings: this.compositor?.warnings ?? [],
    };
  }
}
