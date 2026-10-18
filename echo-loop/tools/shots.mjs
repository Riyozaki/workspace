// Headless browser check: loads the game, records console errors, takes screenshots.
// Usage: node shots.mjs <outDir> [url]
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
const out = process.argv[2] || '/tmp/shots';
const url = process.argv[3] || 'http://127.0.0.1:3000/?seed=12345';
fs.mkdirSync(out, { recursive: true });
const browser = await puppeteer.launch({ executablePath: await chromium.executablePath(), headless: true, args: chromium.args, defaultViewport: { width: 1280, height: 800 } });
const page = await browser.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
await page.goto(url, { waitUntil: 'load' });
await new Promise((r) => setTimeout(r, 800));
await page.screenshot({ path: `${out}/01-menu.png` });
await page.evaluate(() => window.echoLoop.startRun(12345));
await new Promise((r) => setTimeout(r, 600));
await page.screenshot({ path: `${out}/02-floor1.png` });
// walk a few steps with real key presses
for (const k of ['ArrowRight', 'ArrowRight', 'ArrowDown', 'ArrowDown', 'ArrowRight']) {
  await page.keyboard.press(k);
  await new Promise((r) => setTimeout(r, 160));
}
await page.screenshot({ path: `${out}/03-walking.png` });
const state = await page.evaluate(() => ({ mode: window.echoLoop.mode, turn: window.echoLoop.G.turn, pos: window.echoLoop.G.player, hp: window.echoLoop.G.player.hp }));
console.log('state', JSON.stringify(state));
console.log('errors', errors.length ? errors.join('\n') : 'none');
await browser.close();
