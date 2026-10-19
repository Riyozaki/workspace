// @ts-check
import { spawn } from 'node:child_process';

/**
 * Finds a working ffmpeg: explicit path first, then `ffmpeg` on PATH.
 * Probing runs `ffmpeg -version`, so a broken binary is reported, not assumed good.
 * @param {string|undefined} explicit
 * @returns {Promise<string|null>}
 */
export async function resolveFfmpeg(explicit) {
  for (const candidate of [explicit, 'ffmpeg'].filter(Boolean)) {
    if (await probe(/** @type {string} */ (candidate))) return /** @type {string} */ (candidate);
  }
  return null;
}

/** @param {string} bin */
function probe(bin) {
  return new Promise((resolve) => {
    const p = spawn(bin, ['-version'], { stdio: 'ignore' });
    p.on('error', () => resolve(false));
    p.on('close', (code) => resolve(code === 0));
  });
}
