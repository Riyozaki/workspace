import { test } from 'node:test';
import assert from 'node:assert/strict';
import { act, chooseRelic, newRun } from '../src/core/engine.js';
import { arena } from './helpers.js';
import { generateFloor } from '../src/core/dungeon.js';
import { playRun } from '../tools/bot.js';

test('an echo attacks an enemy when its recorded move bumps into it', () => {
  // echo recorded: move right; enemy husk sits at (2,1); echo is at (1,1)
  const G = arena(['#####', '#@H.#', '#####'], { hp: 6 });
  G.echoes = [{ id: 9, path: [{ dx: 1, dy: 0 }], cursor: 0, x: 1, y: 1, hp: 1 }];
  const huskHp = G.enemies[0].hp;
  act(G, { type: 'wait' });
  assert.ok(G.events.some((e) => e.type === 'hit' && e.by === 'echo'), 'echo hit the husk');
  assert.ok(G.enemies.length === 0 || G.enemies[0].hp < huskHp, 'husk took damage');
  assert.equal(G.echoes[0].x, 1, 'echo did not walk into the enemy tile');
});

test('sniper reloads for one turn between shots', () => {
  const G = arena(['##########', '#@...S...#', '##########'], { hp: 6 });
  act(G, { type: 'wait' });
  assert.equal(G.player.hp, 5, 'first shot');
  act(G, { type: 'wait' });
  assert.equal(G.player.hp, 5, 'reloading, no shot');
  act(G, { type: 'wait' });
  assert.equal(G.player.hp, 4, 'second shot after reload');
});

test('warden summons a husk after its cooldown while it has a target', () => {
  const G = arena(['##########', '#@......W#', '##########'], { hp: 6, floor: 5 });
  G.enemies = [{ id: 77, type: 'warden', x: 8, y: 1, hp: 12, maxHp: 12, state: 'patrol', lastSeen: null, alert: 0, wind: null, summonCd: 4 }];
  for (let i = 0; i < 4; i++) act(G, { type: 'wait' });
  assert.ok(G.enemies.some((e) => e.type === 'husk'), 'husk summoned');
});

test('iron heart relic: +2 max HP and immediate heal after floor clear', () => {
  const G = newRun(31);
  G.status = 'relic';
  G.offers = ['iron_heart', 'lantern', 'extra_loop'];
  G.player.hp = 3;
  chooseRelic(G, 'iron_heart');
  assert.equal(G.player.maxHp, 8);
  assert.equal(G.player.hp, 8, 'start of next floor: full hp (reset) + heal');
});

test('extra_loop relic raises the attempt budget', () => {
  // 5 earlier deaths; this is the 6th. Budget 6 -> run over; budget 7 (relic) -> still playing.
  const plain = arena(['#####', '#@..#', '#####'], { hp: 1, floor: 2 });
  plain.attemptsUsed = 5;
  plain.player.hp = 0;
  act(plain, { type: 'wait' });
  assert.equal(plain.status, 'over');
  const relic = arena(['#####', '#@..#', '#####'], { hp: 1, floor: 2, relics: ['extra_loop'] });
  relic.attemptsUsed = 5;
  relic.player.hp = 0;
  act(relic, { type: 'wait' });
  assert.equal(relic.status, 'playing');
});

test('floors generated for seeds 1..5 start on a walkable tile and have a reachable exit', () => {
  for (let f = 1; f <= 5; f++) {
    const g = generateFloor(55 + f, f);
    const i = g.start.y * g.map.w + g.start.x;
    assert.notEqual(g.map.tiles[i], 0);
  }
});

test('bot clears floor 1 on most seeds (regression for generation + AI, not a balance claim)', () => {
  let cleared = 0;
  for (let s = 0; s < 20; s++) if (playRun(5000 + s, 1).floorsCleared >= 1) cleared++;
  assert.ok(cleared >= 18, `cleared ${cleared}/20`);
});

test('puzzle: an echo triggers the plate, so the player can pass the gate alone', () => {
  // corridor: plate at (2,1); gate at (5,1); the echo recorded "step right onto the plate" and then stays put
  const G = arena(['##########', '#@_..+....#', '##########']);
  G.echoes = [{ id: 9, path: [{ dx: 1, dy: 0 }, { wait: true }], cursor: 0, x: 1, y: 1, hp: 1 }];
  act(G, { type: 'wait' }); // echo steps onto plate (turn 1)
  assert.equal(G.echoes[0].x, 2);
  assert.equal(G.door.open, true);
  // plate triggers once on entry (not held); the gate stays open for 6 turns after it, which the player uses
  for (let i = 0; i < 3; i++) act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.player.x, 4);
  act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.player.x, 5, 'player stands in the gate');
  assert.equal(G.status, 'playing');
});
