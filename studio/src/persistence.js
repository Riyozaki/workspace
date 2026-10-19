// @ts-check
import { readFile, writeFile, rename, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { validateProject, ModelError } from './model.js';

/**
 * Loads and validates a project file.
 * @param {string} path
 * @returns {Promise<import('./model.js').Project>}
 */
export async function loadProject(path) {
  let text;
  try {
    text = await readFile(path, 'utf8');
  } catch (err) {
    if (/** @type {NodeJS.ErrnoException} */ (err).code === 'ENOENT') {
      throw new ModelError(`Файл проекта не найден: ${path}`);
    }
    throw new ModelError(`Не удалось прочитать ${path}: ${/** @type {Error} */ (err).message}`);
  }
  let raw;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new ModelError(`Файл ${path} не является корректным JSON.`);
  }
  return validateProject(raw);
}

/**
 * Saves atomically: write to a temp file, then rename over the target, so a
 * crash mid-write never leaves a half-written project behind.
 * @param {string} path
 * @param {import('./model.js').Project} project
 */
export async function saveProject(path, project) {
  await mkdir(dirname(path), { recursive: true });
  const tmp = `${path}.tmp-${process.pid}`;
  await writeFile(tmp, `${JSON.stringify(project, null, 2)}\n`, 'utf8');
  await rename(tmp, path);
}
