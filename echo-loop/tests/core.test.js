import { test } from 'node:test';
import assert from 'node:assert/strict';
import { makeRng, rnd, rint, rshuffle } from '../src/core/rng.js';
import { generateFloor } from '../src/core/dungeon.js';
import { distanceMap, nextStep } from '../src/core/pathfind.js';
import { T, lineClear, isWalkable } from '../src/core/grid.js';
import { computeFov } from '../src/core/fov.js';
import { act, newRun, chooseRelic } from '../src/core/engine.js';
import { modsOf, RELICS } from '../src/core/entities.js';
import { arena, snapshotString } from './helpers.js';

// ---------- RNG ----------
test('rng is deterministic and bounded', () => {
  const a = makeRng(99);
  const b = makeRng(99);
  for (let i = 0; i < 1000; i++) {
    const x = rnd(a);
    assert.equal(x, rnd(b));
    assert.ok(x >= 0 && x < 1);
  }
  const r = makeRng(5);
  for (let i = 0; i < 500; i++) {
    const v = rint(r, 7);
    assert.ok(v >= 0 && v < 7);
  }
  assert.deepEqual(rshuffle(makeRng(1), [1, 2, 3, 4, 5]).sort(), [1, 2, 3, 4, 5]);
});

// ---------- generation guarantees ----------
function reachable(map, from, to, blockDoor) {
  const d = distanceMap({ map }, from.x, from.y, (x, y) => {
    const t = map.tiles[y * map.w + x];
    if (t === T.WALL) return false;
    if (blockDoor && t === T.DOOR) return false;
    return true;
  });
  return d.dist[to.y * map.w + to.x] !== -1;
}

test('every generated floor: exit reachable, gate mandatory, plate reachable without the gate', () => {
  let gatedFloors = 0;
  for (let seed = 1; seed <= 40; seed++) {
    for (let floor = 1; floor <= 5; floor++) {
      const g = generateFloor(seed * 131 + floor, floor);
      assert.ok(reachable(g.map, g.start, g.exit, false), `exit reachable seed=${seed} f=${floor}`);
      assert.notEqual(g.map.tiles[g.exit.y * g.map.w + g.exit.x], T.WALL);
      if (g.gate) {
        gatedFloors++;
        assert.ok(!reachable(g.map, g.start, g.exit, true), `gate mandatory seed=${seed} f=${floor}`);
        assert.ok(reachable(g.map, g.start, g.plate, true), `plate before gate seed=${seed} f=${floor}`);
      } else {
        assert.equal(floor, 1, 'only floor 1 has no gate');
      }
      for (const e of g.enemies) {
        assert.notEqual(g.map.tiles[e.y * g.map.w + e.x], T.WALL);
        assert.ok(Math.abs(e.x - g.start.x) + Math.abs(e.y - g.start.y) >= 7, 'enemies not spawned on top of start');
      }
    }
  }
  assert.ok(gatedFloors > 100);
});

test('generation is deterministic per (seed, floor)', () => {
  const a = generateFloor(777, 3);
  const b = generateFloor(777, 3);
  assert.deepEqual(a.map.tiles, b.map.tiles);
  assert.deepEqual(a.enemies, b.enemies);
  const c = generateFloor(778, 3);
  assert.notDeepEqual(a.map.tiles, c.map.tiles);
});

test('floor 5 has the Warden guarding the exit', () => {
  const g = generateFloor(4242, 5);
  const w = g.enemies.find((e) => e.type === 'warden');
  assert.ok(w, 'warden exists');
  assert.ok(Math.abs(w.x - g.exit.x) + Math.abs(w.y - g.exit.y) <= 2);
});

// ---------- pathfinding / LOS / FOV ----------
test('nextStep finds shortest first step and respects walls', () => {
  const G = arena([
    '#######',
    '#.....#',
    '#.###.#',
    '#.....#',
    '#######',
  ]);
  // (5,1) is 4 steps along the top corridor; the bottom route is longer
  const s = nextStep(G, { x: 1, y: 1 }, { x: 5, y: 1 }, () => false);
  assert.deepEqual(s, { x: 2, y: 1 });
  // a goal on the other side forces the route around the loop; first step is valid & walkable
  const s2 = nextStep(G, { x: 1, y: 1 }, { x: 5, y: 3 }, () => false);
  assert.ok(s2 && G.map.tiles[s2.y * G.map.w + s2.x] !== T.WALL);
  assert.equal(nextStep(G, { x: 1, y: 1 }, { x: 2, y: 2 }, () => false), null, 'wall goal unreachable');
});

test('line of sight is blocked by walls and closed gates only', () => {
  const G = arena(['#########', '#...#...#', '#.......#', '#########']);
  assert.equal(lineClear(G, 1, 1, 6, 1), false, 'wall in between');
  assert.equal(lineClear(G, 1, 2, 7, 2), true, 'open row');
});

test('fov reveals open tiles in view but not tiles hidden behind a wall', () => {
  const G = arena(['#######', '#.#...#', '#.#...#', '#######']);
  const m = computeFov(G, 1, 1, 8);
  assert.equal(m[1 * G.map.w + 1], 1, 'own tile');
  assert.equal(m[1 * G.map.w + 4], 0, 'behind the wall at (2,1)');
  assert.equal(m[2 * G.map.w + 3], 0, 'behind the wall at (2,2)');
});

// ---------- basic turn rules ----------
test('bumping a wall costs no turn; moving costs one and is recorded', () => {
  const G = arena(['#####', '#@..#', '#####']);
  act(G, { type: 'move', dx: 0, dy: -1 });
  assert.equal(G.turn, 0);
  assert.equal(G.record.length, 0);
  act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.turn, 1);
  assert.equal(G.player.x, 2);
  assert.deepEqual(G.record, [{ dx: 1, dy: 0 }]);
});

test('rewind restores the previous tick and consumes a shard', () => {
  const G = arena(['#######', '#@....#', '#######']);
  act(G, { type: 'move', dx: 1, dy: 0 });
  act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.player.x, 3);
  act(G, { type: 'rewind' });
  assert.equal(G.player.x, 2);
  assert.equal(G.player.shards, 0);
  assert.equal(G.turn, 1);
  act(G, { type: 'rewind' });
  assert.equal(G.player.x, 2, 'no shard left -> rewind is a no-op');
  assert.equal(G.turn, 1);
});

test('rewind also rewinds echoes and enemies (full snapshot)', () => {
  const G = arena(['##########', '#@....H...#', '##########'], { shards: 3, hp: 6 });
  act(G, { type: 'move', dx: 1, dy: 0 });
  const huskX = G.enemies[0].x;
  act(G, { type: 'wait' });
  act(G, { type: 'rewind' });
  assert.equal(G.enemies[0].x, huskX, 'enemy position restored');
  assert.equal(G.turn, 1);
  assert.equal(G.record.length, 1);
});

test('exit: reaching it moves to relic selection, relic applies, next floor starts', () => {
  const G = arena(['#####', '#@>.#', '#####'], { floor: 1 });
  act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.status, 'relic');
  assert.equal(G.clearedFloors, 1);
  G.offers = ['iron_heart', 'lantern', 'echo_edge'];
  chooseRelic(G, 'iron_heart');
  assert.equal(G.floor, 2);
  assert.equal(G.status, 'playing');
  assert.equal(G.player.maxHp, 8);
  assert.ok(G.relics.includes('iron_heart'));
});

// ---------- enemy AI ----------
test('husk chases and attacks when adjacent', () => {
  const G = arena(['#########', '#@......#', '#H.....##', '#########'], { hp: 6 });
  // husk at (1,2) is adjacent to player at (1,1)
  act(G, { type: 'wait' });
  assert.equal(G.player.hp, 5);
});

test('husk walks toward a visible player', () => {
  const G = arena(['##########', '#@.....H.#', '##########']);
  const before = G.enemies[0].x;
  act(G, { type: 'wait' });
  assert.equal(G.enemies[0].x, before - 1);
  assert.equal(G.enemies[0].state, 'chase');
});

test('sniper shoots along a clear line and does not shoot when unaligned', () => {
  const G = arena(['##########', '#@...S...#', '##########'], { hp: 6 });
  act(G, { type: 'wait' });
  assert.equal(G.player.hp, 5, 'sniper aligned at distance 4 -> shot');
  assert.ok(G.events.some((e) => e.type === 'shot'));

  const G2 = arena(['#####', '#@..#', '#..S#', '#####'], { hp: 6 });
  act(G2, { type: 'wait' });
  assert.equal(G2.player.hp, 6, 'not aligned -> no shot');
});

test('charger telegraphs for one tick, then charges in the locked direction', () => {
  const G = arena(['##########', '#@..C....#', '##########'], { hp: 6 });
  act(G, { type: 'wait' }); // charger sees player at distance 3, aligned -> windup
  const ch = G.enemies[0];
  assert.ok(ch.wind, 'windup set');
  assert.equal(ch.wind.dx, -1);
  assert.equal(G.player.hp, 6);
  act(G, { type: 'wait' }); // charge: hits player on the way
  assert.equal(G.player.hp, 4, 'charge hits for 2');
});

test('player bump attack damages and kills enemies; noise alerts nearby ones', () => {
  const G = arena(['#######', '#@H...#', '#.....#', '#######'], { hp: 6 });
  act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.enemies[0].hp, 1, 'husk 3hp - 2 dmg');
  act(G, { type: 'move', dx: 1, dy: 0 });
  assert.equal(G.enemies.length, 0, 'husk dead');
  assert.equal(G.kills, 1);
});

// ---------- echoes and loops ----------
test('death creates an echo from the recorded life and resets the floor', () => {
  // player walks right into a husk at (4,1) that hits for 1; start hp=1
  const G = arena(['#######', '#@..H.#', '#.....#', '#######'], { hp: 1 });
  act(G, { type: 'move', dx: 1, dy: 0 }); // (2,1); husk steps to (3,1)
  act(G, { type: 'move', dx: 1, dy: 0 }); // bump attack on husk; husk hits back -> dead
  assert.equal(G.echoes.length, 1, 'echo created');
  assert.deepEqual(G.echoes[0].path, [{ dx: 1, dy: 0 }, { dx: 1, dy: 0 }]);
  assert.equal(G.attemptsUsed, 1);
  assert.equal(G.player.x, 1, 'player back at start');
  assert.equal(G.player.hp, 6, 'hp restored in new loop');
  assert.equal(G.enemies.length, 1, 'husk respawned by floor reset');
  assert.equal(G.echoes[0].x, 1);
});

test('echo replays its recorded moves in the next life and can attack', () => {
  const G = arena(['##########', '#@....H...#', '##########'], { hp: 6, floor: 2 });
  // life 1: walk right 2 steps, then die by force
  act(G, { type: 'move', dx: 1, dy: 0 });
  act(G, { type: 'move', dx: 1, dy: 0 });
  G.player.hp = 0;
  act(G, { type: 'wait' }); // death at end of tick (hp<=0 check)
  assert.equal(G.echoes.length, 1);
  // life 2: echo should be at start; after 1 tick it moves right
  assert.equal(G.echoes[0].x, 1);
  act(G, { type: 'wait' });
  assert.equal(G.echoes[0].x, 2, 'echo replays first recorded move');
  act(G, { type: 'wait' });
  assert.equal(G.echoes[0].x, 3, 'second recorded move');
});

test('enemies kill echoes in melee', () => {
  const G = arena(['#####', '#@.H#', '#####'], { hp: 6 });
  G.echoes = [{ id: 9, path: [{ dx: 1, dy: 0 }], cursor: 0, x: 2, y: 1, hp: 1 }];
  act(G, { type: 'wait' });
  assert.equal(G.echoes.length, 0, 'echo killed by husk adjacent');
});

test('echo cap drops the oldest echo', () => {
  const G = arena(['#####', '#@..#', '#####'], { hp: 1, floor: 2 });
  G.echoes = [
    { id: 1, path: [{ wait: true }], cursor: 0, x: 1, y: 1, hp: 1 },
    { id: 2, path: [{ wait: true }], cursor: 0, x: 1, y: 1, hp: 1 },
    { id: 3, path: [{ wait: true }], cursor: 0, x: 1, y: 1, hp: 1 },
  ];
  G.enemies = [{ id: 50, type: 'husk', x: 2, y: 1, hp: 3, maxHp: 3, state: 'patrol', lastSeen: null, alert: 0, wind: null, summonCd: 4 }];
  act(G, { type: 'move', dx: 1, dy: 0 }); // now adjacent to the husk
  act(G, { type: 'wait' });
  assert.equal(G.echoes.length, 3);
  assert.ok(G.echoes.every((e) => e.id !== 1), 'oldest (id 1) dissolved');
});

test('exhausting loop attempts ends the run', () => {
  const G = arena(['#####', '#@..#', '#####'], { hp: 1, floor: 2 });
  G.attemptsUsed = 5; // budget is 6 by default
  G.player.hp = 0;
  act(G, { type: 'wait' });
  assert.equal(G.status, 'over');
});

// ---------- gate & plate ----------
test('stepping on a plate opens the gate for 6 turns, then it closes again', () => {
  const G = arena(['#########', '#@_+....#', '#########']);
  act(G, { type: 'move', dx: 1, dy: 0 }); // onto plate at turn 1 -> open through turn 7
  assert.equal(G.door.open, true);
  for (let i = 0; i < 6; i++) act(G, { type: 'wait' }); // turns 2..7
  assert.equal(G.turn, 7);
  assert.equal(G.door.open, true);
  act(G, { type: 'wait' }); // turn 8
  assert.equal(G.door.open, false);
});

test('a unit standing in the gate keeps it open', () => {
  const G = arena(['#########', '#@_+....#', '#########']);
  G.door.openUntil = -1;
  G.player.x = 3;
  G.player.y = 1;
  G.door.open = false;
  act(G, { type: 'wait' });
  assert.equal(G.door.open, true);
});

// ---------- determinism ----------
test('same seed + same inputs => identical state', () => {
  const script = [{ type: 'move', dx: 1, dy: 0 }, { type: 'wait' }, { type: 'move', dx: 0, dy: 1 }, { type: 'move', dx: 0, dy: 1 }, { type: 'wait' }, { type: 'move', dx: 1, dy: 0 }];
  const run = () => {
    const G = newRun(2024);
    for (let i = 0; i < 3; i++) for (const a of script) act(G, a);
    return snapshotString(G);
  };
  assert.equal(run(), run());
});

test('modsOf stacks relic effects', () => {
  const m = modsOf(['second_echo', 'second_echo', 'iron_heart', 'lantern', 'sharp_steel', 'extra_loop']);
  assert.equal(m.maxEchoes, 5);
  assert.equal(m.maxHp, 8);
  assert.equal(m.lantern, 10);
  assert.equal(m.playerDmg, 3);
  assert.equal(m.attempts, 7);
  assert.equal(RELICS.length, 7);
});
