// @ts-check
import { createCanvas, Image, loadImage } from '@napi-rs/canvas';
import { readFileSync } from 'node:fs';

/** @typedef {import('./model.js').Scene} Scene
 *  @typedef {import('./model.js').Source} Source */

/**
 * Draws scenes onto an RGBA canvas.
 *
 * Two strategies are kept on purpose so the benchmark can compare them:
 *  - `cache: false` ("baseline"): every frame re-reads image files from disk and
 *    re-rasterises text/colour layers. This is the straightforward approach.
 *  - `cache: true` (default): images are decoded once and each text/colour layer
 *    is rasterised once into its own offscreen canvas, keyed by a content
 *    signature. A frame is then just a sequence of drawImage calls.
 */
export class Compositor {
  /**
   * @param {{ width: number, height: number, cache?: boolean }} opts
   */
  constructor({ width, height, cache = true }) {
    this.width = width;
    this.height = height;
    this.cache = cache;
    this.out = createCanvas(width, height);
    this.outCtx = this.out.getContext('2d');
    /** @type {Map<string, any>} decoded images by path */
    this.images = new Map();
    /** @type {Map<string, any>} rasterised layers by signature */
    this.layers = new Map();
    /** @type {string[]} */
    this.warnings = [];
  }

  /**
   * Loads every image source referenced by the scene ahead of time so that
   * rendering itself never blocks on I/O. Missing files become warnings, not crashes.
   * @param {Scene} scene
   */
  async prepare(scene) {
    if (!this.cache) return;
    for (const item of scene.items) {
      if (item.kind !== 'image' || !item.path || this.images.has(item.path)) continue;
      try {
        this.images.set(item.path, await loadImage(item.path));
      } catch (err) {
        this.warnings.push(`Не удалось загрузить изображение «${item.name}»: ${/** @type {Error} */ (err).message}`);
        this.images.set(item.path, null);
      }
    }
  }

  /**
   * @param {Source} item
   * @returns {string}
   */
  static signature(item) {
    return [item.kind, item.w, item.h, item.color, item.text, item.fontSize, item.path].join('|');
  }

  /**
   * Rasterises a text or colour layer into an offscreen canvas.
   * @param {Source} item
   */
  rasterise(item) {
    const c = createCanvas(item.w, item.h);
    const g = c.getContext('2d');
    if (item.kind === 'color') {
      g.fillStyle = item.color ?? '#000';
      g.fillRect(0, 0, item.w, item.h);
    } else if (item.kind === 'text') {
      g.fillStyle = item.color ?? '#fff';
      g.font = `${item.fontSize ?? 48}px sans-serif`;
      g.textBaseline = 'middle';
      const lines = (item.text ?? '').split('\n');
      const lh = (item.fontSize ?? 48) * 1.2;
      const top = item.h / 2 - ((lines.length - 1) * lh) / 2;
      lines.forEach((line, i) => g.fillText(line, 8, top + i * lh, item.w - 16));
    }
    return c;
  }

  /**
   * Draws one source into the output context.
   * @param {Source} item
   * @param {any} g
   */
  drawItem(item, g) {
    if (item.kind === 'image') {
      let img;
      if (this.cache) {
        img = this.images.get(item.path ?? '');
      } else if (item.path) {
        // Baseline: decode from disk on every frame.
        img = null;
        try {
          img = loadImageSync(item.path);
        } catch {
          img = null;
        }
      }
      if (img) g.drawImage(img, item.x, item.y, item.w, item.h);
      return;
    }
    if (this.cache) {
      const sig = Compositor.signature(item);
      let layer = this.layers.get(sig);
      if (!layer) {
        layer = this.rasterise(item);
        this.layers.set(sig, layer);
      }
      g.drawImage(layer, item.x, item.y);
    } else {
      g.drawImage(this.rasterise(item), item.x, item.y);
    }
  }

  /**
   * Renders the scene and returns the output canvas (valid until the next call).
   * @param {Scene} scene
   * @returns {any}
   */
  render(scene) {
    const g = this.outCtx;
    g.fillStyle = '#000';
    g.fillRect(0, 0, this.width, this.height);
    for (const item of scene.items) {
      if (!item.visible) continue;
      this.drawItem(item, g);
    }
    return this.out;
  }

  /** Drops cached layers that no longer correspond to any source (bounded memory). */
  pruneLayers(scenes) {
    const live = new Set();
    for (const s of scenes) for (const it of s.items) live.add(Compositor.signature(it));
    for (const key of this.layers.keys()) if (!live.has(key)) this.layers.delete(key);
  }

  /** @returns {Buffer} JPEG-encoded current frame (for the preview). */
  encodeJpeg(quality = 80) {
    return this.out.toBuffer('image/jpeg', quality);
  }
}

/**
 * Baseline-only synchronous decode: reads the file and decodes it on the spot,
 * which is the per-frame cost the naive design pays.
 * @param {string} path
 */
function loadImageSync(path) {
  const img = new Image();
  img.src = readFileSync(path);
  return img;
}
