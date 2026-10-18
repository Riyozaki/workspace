// Game engine: one call to act() = one player tick. Pure logic, no DOM.
//
// Turn order per tick:  player action -> echoes (replay recorded actions) -> enemies (AI) -> gate update -> death check.
// A life that ends in death becomes an echo (its recorded actions), then the floor resets to its
// initial state. The floor is generated from a fixed seed, so resets are exact.
import { generateFloor } from './dungeon.js';
import { makeRng, rshuffle } from './rng.js';
import { T, inBounds, isWalkable, tileAt, manhattan } from './grid.js';
import { enemyTurn, enemyAt, newEnemy, ALERT_TURNS } from './ai.js';
import { modsOf, RELICS, FLOOR_COUNT, PLAYER_BASE } from './entities.js';

// Fields that are not part of the rewindable snapshot: UI/bookkeeping and static floor data
// (the map, rooms and generated spawn lists never change during a floor's lifetime).
const NON_SNAPSHOT = ['history', 'events', 'log', 'explored', 'map', 'rooms', 'genEnemies', 'genItems', 'start', 'exit', 'gate', 'plate', 'floorSeed'];

export function newRun(seed = Date.now() >>> 0) {
  const G = {
    seed: seed >>> 0,
    rng: makeRng((seed ^ 0x9e3779b9) >>> 0),
    status: 'playing', // playing | relic | won | over
    floor: 1,
    clearedFloors: 0,
    relics: [],
    offers: null,
    attemptsUsed: 0,
    turn: 0,
    kills: 0,
    nextId: 1,
    echoes: [],
    record: [],
    history: [],
    events: [],
    log: [],
    explored: null,
    map: null,
    start: null,
    exit: null,
    gate: null,
    plate: null,
    door: { x: -1, y: -1, open: false, openUntil: -1 },
    enemies: [],
    items: [],
    player: null,
  };
  startFloor(G, 1);
  G.log.push(`Floor ${G.floor}. Loop 1/${mods(G).attempts}.`);
  return G;
}

export const mods = (G) => modsOf(G.relics);

function startFloor(G, floor) {
  G.floor = floor;
  G.floorSeed = (G.seed * 1000003 + floor * 7919) >>> 0;
  G.attemptsUsed = 0;
  G.echoes = [];
  G.explored = null;
  const gen = generateFloor(G.floorSeed, floor);
  G.map = gen.map;
  G.start = gen.start;
  G.exit = gen.exit;
  G.gate = gen.gate;
  G.plate = gen.plate;
  G.explored = new Array(G.map.w * G.map.h).fill(0);
  G.rooms = gen.rooms;
  G.genEnemies = gen.enemies;
  G.genItems = gen.items;
  resetLife(G);
  if (floor === 1) G.log.push('Tip: when you die, your life becomes an echo that replays your moves.');
  if (G.gate) G.log.push('Gate ahead: step on the rune plate to open it for 6 turns. An echo can trigger it for you.');
}

/** Reset the world to the floor's initial state. Echoes persist and respawn at the start. */
function resetLife(G) {
  const m = mods(G);
  G.turn = 0;
  G.record = [];
  G.history = [];
  G.events = [];
  G.enemies = G.genEnemies.map((e) => newEnemy(G.nextId++, e.type, e.x, e.y));
  G.items = G.genItems.map((it) => ({ id: G.nextId++, type: it.type, x: it.x, y: it.y }));
  G.door = { x: G.gate ? G.gate.x : -1, y: G.gate ? G.gate.y : -1, open: false, openUntil: -1 };
  G.player = {
    x: G.start.x,
    y: G.start.y,
    hp: m.maxHp,
    maxHp: m.maxHp,
    shards: m.shards,
    potions: 0,
  };
  for (const e of G.echoes) {
    e.x = G.start.x;
    e.y = G.start.y;
    e.cursor = 0;
    e.hp = 1;
  }
  G.status = 'playing';
  updateGate(G);
}

// ---------- public API ----------

/**
 * action: {type:'move', dx, dy} | {type:'wait'} | {type:'potion'} | {type:'rewind'}
 * Mutates and returns G.
 */
export function act(G, action) {
  G.events = [];
  if (G.status !== 'playing') return G;

  if (action.type === 'rewind') return rewind(G);

  if (action.type === 'move') {
    const nx = G.player.x + action.dx;
    const ny = G.player.y + action.dy;
    if (!inBounds(G.map, nx, ny)) return G;
    const blocked = !isWalkable(G, nx, ny) && !enemyAt(G, nx, ny);
    if (blocked) {
      G.log.push('Path blocked.');
      return G; // bumping a wall costs nothing
    }
  }
  if (action.type === 'potion') {
    if (G.player.potions <= 0) {
      G.log.push('No potions.');
      return G;
    }
    if (G.player.hp >= G.player.maxHp) {
      G.log.push('HP is already full.');
      return G;
    }
  }

  pushHistory(G);
  G.turn++;

  // 1. player
  if (action.type === 'move') {
    G.record.push({ dx: action.dx, dy: action.dy });
    stepUnit(G, G.player, action.dx, action.dy, 'player');
  } else {
    G.record.push({ wait: true });
    if (action.type === 'potion') {
      G.player.potions--;
      const before = G.player.hp;
      G.player.hp = Math.min(G.player.maxHp, G.player.hp + PLAYER_BASE.potionHeal);
      G.events.push({ type: 'heal', x: G.player.x, y: G.player.y, amount: G.player.hp - before });
    }
  }
  if (G.status === 'relic' || G.status === 'won') return G; // reached the exit

  // 2. echoes replay their recorded actions (cyclic)
  for (const ech of G.echoes) {
    if (ech.hp <= 0 || ech.path.length === 0) continue;
    const step = ech.path[ech.cursor % ech.path.length];
    ech.cursor++;
    if (step.wait) continue;
    stepUnit(G, ech, step.dx, step.dy, 'echo');
  }

  // 3. enemies
  for (const e of G.enemies) {
    if (e.hp > 0) enemyTurn(G, e, G.events);
  }

  // 4. cleanup + gate + death
  G.enemies = G.enemies.filter((e) => e.hp > 0);
  G.echoes = G.echoes.filter((e) => e.hp > 0);
  updateGate(G);
  if (G.player.hp <= 0) endLife(G);
  return G;
}

/** Unit (player or echo) tries to move/attack by (dx,dy). Returns result string. */
function stepUnit(G, unit, dx, dy, who) {
  const nx = unit.x + dx;
  const ny = unit.y + dy;
  if (!inBounds(G.map, nx, ny)) return 'blocked';
  const foe = enemyAt(G, nx, ny);
  if (foe) {
    const dmg = who === 'player' ? mods(G).playerDmg : mods(G).echoDmg;
    foe.hp -= dmg;
    G.events.push({ type: 'hit', target: 'enemy', id: foe.id, x: nx, y: ny, amount: dmg, by: who });
    if (who === 'player') noise(G, nx, ny, 5);
    if (foe.hp <= 0) {
      G.events.push({ type: 'death', target: 'enemy', id: foe.id, enemy: foe.type, x: nx, y: ny });
      if (who === 'player') G.kills++;
    } else if (foe.state !== 'chase') {
      foe.state = 'alert';
      foe.lastSeen = who === 'player' ? { x: G.player.x, y: G.player.y } : { x: unit.x, y: unit.y };
      foe.alert = ALERT_TURNS;
    }
    return 'attacked';
  }
  if (!isWalkable(G, nx, ny)) return 'blocked';
  const from = { x: unit.x, y: unit.y };
  unit.x = nx;
  unit.y = ny;
  G.events.push({ type: 'move', unit: who, id: unit.id ?? null, from, to: { x: nx, y: ny } });
  const t = tileAt(G.map, nx, ny);
  if (t === T.PLATE) {
    G.door.openUntil = G.turn + PLAYER_BASE.gateOpenTurns;
    G.events.push({ type: 'plate', x: nx, y: ny, by: who });
    updateGate(G);
  }
  if (who === 'player') {
    if (t === T.EXIT) {
      G.events.push({ type: 'exit', x: nx, y: ny });
      onFloorClear(G);
      return 'moved';
    }
    const it = G.items.findIndex((i) => i.x === nx && i.y === ny);
    if (it !== -1) {
      const item = G.items[it];
      G.items.splice(it, 1);
      if (item.type === 'potion') G.player.potions++;
      if (item.type === 'shard') G.player.shards++;
      G.events.push({ type: 'pickup', item: item.type, x: nx, y: ny });
    }
  }
  return 'moved';
}

/** Enemies within r (manhattan) become alert and head toward the noise. */
function noise(G, x, y, r) {
  for (const e of G.enemies) {
    if (e.hp <= 0) continue;
    if (manhattan(e.x, e.y, x, y) <= r && e.state === 'patrol') {
      e.state = 'alert';
      e.alert = ALERT_TURNS;
      e.lastSeen = { x, y };
    }
  }
}

function updateGate(G) {
  if (!G.gate) return;
  const occupied = (G.player.hp > 0 && G.player.x === G.gate.x && G.player.y === G.gate.y) || !!G.echoes.find((e) => e.hp > 0 && e.x === G.gate.x && e.y === G.gate.y) || !!enemyAt(G, G.gate.x, G.gate.y);
  G.door.open = G.turn <= G.door.openUntil || occupied;
}

function endLife(G) {
  // death -> the recorded life becomes an echo (cap = mods.maxEchoes, oldest dissolves)
  if (G.record.length > 0) {
    G.echoes.push({ id: G.nextId++, path: G.record.slice(), cursor: 0, x: G.start.x, y: G.start.y, hp: 1 });
    while (G.echoes.length > mods(G).maxEchoes) G.echoes.shift();
  }
  G.attemptsUsed++;
  G.events.push({ type: 'loop_lost', attempt: G.attemptsUsed });
  const budget = mods(G).attempts;
  if (G.attemptsUsed >= budget) {
    G.status = 'over';
    G.log.push(`Loops exhausted on floor ${G.floor}. Run over.`);
    return;
  }
  resetLife(G);
  G.log.push(`Loop ${G.attemptsUsed + 1}/${budget}: ${G.echoes.length} echo(es) with you.`);
  G.events.push({ type: 'loop_start', attempt: G.attemptsUsed + 1 });
}

function onFloorClear(G) {
  G.clearedFloors++;
  if (G.floor >= FLOOR_COUNT) {
    G.status = 'won';
    G.log.push('Floor 5 cleared. Victory!');
    return;
  }
  G.status = 'relic';
  // offers: 3 distinct relics chosen at random (owned relics can be offered again and stack)
  const pool = rshuffle(G.rng, RELICS.map((r) => r.id));
  G.offers = pool.slice(0, 3);
}

/** Choose a relic after clearing a floor, then descend. */
export function chooseRelic(G, id) {
  if (G.status !== 'relic' || !G.offers.includes(id)) return G;
  G.relics.push(id);
  G.offers = null;
  startFloor(G, G.floor + 1);
  if (id === 'iron_heart') G.player.hp = Math.min(G.player.maxHp, G.player.hp + 2);
  G.log.push(`Floor ${G.floor}. Loop 1/${mods(G).attempts}.`);
  G.events = [{ type: 'floor', floor: G.floor }];
  return G;
}

function rewind(G) {
  if (G.player.shards <= 0 || G.history.length === 0) {
    G.log.push('No rewind shards or history left.');
    return G;
  }
  const prev = G.history.pop();
  const { recLen, echoes, ...rest } = prev;
  Object.assign(G, structuredClone(rest));
  G.echoes = echoes.map((e) => ({ ...e }));
  G.record.length = recLen;
  G.player.shards = Math.max(0, G.player.shards - 1);
  G.events = [{ type: 'rewind' }];
  G.log.push('Rewound one turn.');
  return G;
}

// The life record is append-only and echo paths are immutable, so snapshots store only
// the record length and share the path arrays. This keeps per-tick snapshots O(state).
function snapshotOf(G) {
  const snap = {};
  for (const k of Object.keys(G)) if (!NON_SNAPSHOT.includes(k) && k !== 'record' && k !== 'echoes') snap[k] = G[k];
  const copy = structuredClone(snap);
  copy.recLen = G.record.length;
  copy.echoes = G.echoes.map((e) => ({ ...e }));
  return copy;
}

function pushHistory(G) {
  G.history.push(snapshotOf(G));
  if (G.history.length > 200) G.history.shift();
}

