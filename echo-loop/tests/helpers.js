import { newRun } from '../src/core/engine.js';
import { newEnemy } from '../src/core/ai.js';
import { T } from '../src/core/grid.js';
import { modsOf } from '../src/core/entities.js';

/**
 * Build a hand-made test arena from ASCII rows.
 * '#' wall, '.' floor, '@' player start, '>' exit, '_' plate, '+' gate (door),
 * 'H' husk, 'S' sniper, 'C' charger, 'E' echo-less (ignored), 'p' potion, 'x' shard.
 */
export function arena(rows, opts = {}) {
  const h = rows.length;
  const w = rows[0].length;
  const G = newRun(opts.seed ?? 7);
  const tiles = [];
  let start = null;
  let exit = null;
  let gate = null;
  let plate = null;
  const enemies = [];
  const items = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const c = rows[y][x];
      let t = T.FLOOR;
      if (c === '#') t = T.WALL;
      if (c === '>') {
        t = T.EXIT;
        exit = { x, y };
      }
      if (c === '_') {
        t = T.PLATE;
        plate = { x, y };
      }
      if (c === '+') {
        t = T.DOOR;
        gate = { x, y };
      }
      if (c === '@') start = { x, y };
      if (c === 'H' || c === 'S' || c === 'C') enemies.push({ type: { H: 'husk', S: 'sniper', C: 'charger' }[c], x, y });
      if (c === 'p') items.push({ id: 900 + items.length, type: 'potion', x, y });
      if (c === 'x') items.push({ id: 900 + items.length, type: 'shard', x, y });
      tiles.push(t);
    }
  }
  G.map = { w, h, tiles };
  G.start = start ?? { x: 1, y: 1 };
  G.exit = exit ?? { x: w - 2, y: h - 2 };
  G.gate = gate;
  G.plate = plate;
  G.door = { x: gate ? gate.x : -1, y: gate ? gate.y : -1, open: false, openUntil: -1 };
  G.explored = new Array(w * h).fill(0);
  G.genEnemies = enemies;
  G.genItems = items;
  G.floor = opts.floor ?? 2;
  G.relics = opts.relics ?? [];
  G.enemies = enemies.map((e, i) => newEnemy(100 + i, e.type, e.x, e.y));
  G.items = items.slice();
  G.player = { x: G.start.x, y: G.start.y, hp: opts.hp ?? 6, maxHp: opts.maxHp ?? modsOf(G.relics).maxHp, shards: opts.shards ?? 1, potions: opts.potions ?? 0 };
  G.echoes = opts.echoes ?? [];
  G.nextId = 500;
  G.turn = 0;
  G.record = [];
  G.history = [];
  G.events = [];
  G.log = [];
  G.status = 'playing';
  G.attemptsUsed = 0;
  G.clearedFloors = 0;
  G.kills = 0;
  G.offers = null;
  G.rng = { s: 1234 };
  // gate state for a plate
  if (gate) G.door.open = false;
  return G;
}

export function snapshotString(G) {
  const { history, events, log, explored, ...rest } = G;
  return JSON.stringify(rest);
}
