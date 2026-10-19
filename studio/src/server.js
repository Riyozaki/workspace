// @ts-check
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, sep } from 'node:path';
import { dispatch, CommandError } from './actions.js';
import { DEFAULT_BINDINGS } from './hotkeys.js';

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
const MAX_BODY = 1024 * 1024;

/**
 * HTTP layer: static UI + a small JSON command API. No business logic here.
 * @param {{ ctx: { store: any, engine: any, projectPath?: string }, publicDir: string }} opts
 */
export function createAppServer({ ctx, publicDir }) {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? '/', 'http://localhost');
      if (req.method === 'GET' && url.pathname === '/api/project') {
        return sendJson(res, 200, ctx.store.project);
      }
      if (req.method === 'GET' && url.pathname === '/api/hotkeys') {
        return sendJson(res, 200, DEFAULT_BINDINGS);
      }
      if (req.method === 'GET' && url.pathname === '/api/preview.jpg') {
        const jpg = ctx.engine.preview;
        if (!jpg) { res.writeHead(204); return res.end(); }
        res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Cache-Control': 'no-store' });
        return res.end(jpg);
      }
      if (req.method === 'POST' && url.pathname === '/api/command') {
        const body = await readJson(req);
        if (typeof body.type !== 'string') return sendJson(res, 400, { error: 'Нет поля type.', code: 'bad-request' });
        try {
          const result = await dispatch(ctx, body.type, body.args ?? {});
          return sendJson(res, 200, { ok: true, result, project: ctx.store.project });
        } catch (err) {
          if (err instanceof CommandError) return sendJson(res, 422, { error: err.message, code: err.code });
          throw err;
        }
      }
      if (req.method === 'GET' || req.method === 'HEAD') return serveStatic(url.pathname, publicDir, res);
      res.writeHead(405); res.end();
    } catch (err) {
      const e = /** @type {Error & {code?:string}} */ (err);
      const status = e.code === 'bad-json' || e.code === 'too-large' ? 400 : 500;
      sendJson(res, status, { error: status === 500 ? 'Внутренняя ошибка сервера.' : e.message, code: e.code ?? 'internal' });
      if (status === 500) console.error(err);
    }
  });
}

/** @param {import('node:http').ServerResponse} res @param {number} status @param {unknown} body */
function sendJson(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(data) });
  res.end(data);
}

/** @param {import('node:http').IncomingMessage} req */
function readJson(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = /** @type {Buffer[]} */ ([]);
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) { reject(Object.assign(new Error('Слишком большой запрос.'), { code: 'too-large' })); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => {
      try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); }
      catch { reject(Object.assign(new Error('Тело запроса — не JSON.'), { code: 'bad-json' })); }
    });
    req.on('error', reject);
  });
}

/**
 * @param {string} pathname @param {string} publicDir @param {import('node:http').ServerResponse} res
 */
async function serveStatic(pathname, publicDir, res) {
  const rel = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const full = normalize(join(publicDir, rel));
  if (!full.startsWith(normalize(publicDir + sep))) { res.writeHead(403); return res.end(); }
  try {
    const data = await readFile(full);
    res.writeHead(200, { 'Content-Type': MIME[extname(full)] ?? 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Не найдено');
  }
}
