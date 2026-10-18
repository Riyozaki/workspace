// End-to-end in real Chromium: bot plays through the UI API, screenshots key screens, clicks a relic card.
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
const out = process.argv[2];
const base = process.argv[3] || 'http://127.0.0.1:3000';
fs.mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: await chromium.executablePath(), headless: true, args: chromium.args, defaultViewport: { width: 1280, height: 800 } });
const page = await browser.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
await page.goto(base + '/?seed=777', { waitUntil: 'load' });
await sleep(500);
await page.click('#btn-start');
await sleep(300);
const report = {};
// 1) play floor 1 with the bot
report.floor1 = await page.evaluate(async () => {
  const { botAction } = await import('/tools/bot.js');
  let n = 0;
  while (window.echoLoop.mode === 'play' && n < 20000) {
    window.echoLoop.act(botAction(window.echoLoop.G));
    n++;
  }
  return { ticks: n, mode: window.echoLoop.mode, floor: window.echoLoop.G.floor, status: window.echoLoop.G.status };
});
await sleep(300);
await page.screenshot({ path: `${out}/10-relic-choice.png` });
// click a relic card with the mouse
await page.click('.relic-card');
await sleep(400);
report.afterRelic = await page.evaluate(() => ({ mode: window.echoLoop.mode, floor: window.echoLoop.G.floor, relics: window.echoLoop.G.relics }));
await page.screenshot({ path: `${out}/11-floor2-start.png` });
// 2) play a few bot ticks on floor 2, then FORCE a death (test harness: hp=0) to show the loop break + echo
report.loopBreak = await page.evaluate(async () => {
  const { botAction } = await import('/tools/bot.js');
  for (let i = 0; i < 6; i++) window.echoLoop.act(botAction(window.echoLoop.G));
  const before = window.echoLoop.G.record.length;
  window.echoLoop.G.player.hp = 0; // forced death (test only)
  window.echoLoop.act({ type: 'wait' });
  return { recordedMoves: before, attemptsUsed: window.echoLoop.G.attemptsUsed, echoes: window.echoLoop.G.echoes.map(e => e.path.length), mode: window.echoLoop.mode };
});
await sleep(120);
await page.screenshot({ path: `${out}/12-loop-broken.png` });
await sleep(1200);
// a few real key presses while an echo replays
for (const k of ['ArrowRight', 'ArrowDown', 'ArrowDown', 'Space']) { await page.keyboard.press(k); await sleep(150); }
await page.screenshot({ path: `${out}/13-echo-replay.png` });
// 3) play until game over or relic/won, collect end-state
report.rest = await page.evaluate(async () => {
  const { botAction } = await import('/tools/bot.js');
  let n = 0;
  while (window.echoLoop.mode === 'play' && n < 40000) {
    window.echoLoop.act(botAction(window.echoLoop.G));
    n++;
  }
  return { ticks: n, mode: window.echoLoop.mode, floor: window.echoLoop.G.floor, status: window.echoLoop.G.status, attempts: window.echoLoop.G.attemptsUsed };
});
await sleep(400);
await page.screenshot({ path: `${out}/14-end-state.png` });
report.errors = errors;
console.log(JSON.stringify(report, null, 1));
await browser.close();
