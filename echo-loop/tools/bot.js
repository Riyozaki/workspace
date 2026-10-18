// Heuristic bot that plays through the real engine. Used to check that floors are
// clearable, how many loops they take, and to get balance numbers.
// Usage: node tools/bot.js [runs=50] [maxFloor=5]
import { newRun, act, chooseRelic } from '../src/core/engine.js';
import { nextStep, distanceMap } from '../src/core/pathfind.js';
import { T, DIRS, isWalkable } from '../src/core/grid.js';
import { RELICS } from '../src/core/entities.js';
import { enemyAt } from '../src/core/ai.js';

/** Choose the next action for a simple strategy: kill adjacent foes, go to plate if the gate is needed, then exit. */
export function botAction(G) {
  const p = G.player;
  // attack adjacent enemy if any (prefer weakest)
  let adj = null;
  for (const d of DIRS) {
    const e = enemyAt(G, p.x + d.dx, p.y + d.dy);
    if (e && (!adj || e.hp < adj.e.hp)) adj = { e, d };
  }
  if (adj) return { type: 'move', dx: adj.d.dx, dy: adj.d.dy };
  // potion when low
  if (p.hp <= 2 && p.potions > 0) return { type: 'potion' };
  // enemies are not walls: stepping into one attacks it (engine handles that)
  const blockedFn = null;
  // goal: exit if reachable from here with the gate closed (i.e. we are already on the exit side)
  let goal = G.exit;
  if (G.gate) {
    const exitSideReach = distanceMap(G, p.x, p.y, (x, y) => {
      const t = G.map.tiles[y * G.map.w + x];
      return t !== 0 && t !== 2; // not WALL, not DOOR
    });
    const exitReachable = exitSideReach.dist[G.exit.y * G.map.w + G.exit.x] !== -1;
    if (!exitReachable) {
      // still on the start side: the gate must be opened by standing on the plate
      if (G.door.open) goal = G.exit; // gate currently open, rush through
      else if (p.x === G.plate.x && p.y === G.plate.y) goal = G.gate;
      else goal = G.plate;
    }
  }
  // item pickup nearby
  const near = G.items.find((it) => Math.abs(it.x - p.x) + Math.abs(it.y - p.y) <= 3);
  if (near && goal === G.exit) goal = near;
  const step = nextStep(G, p, goal, blockedFn, 1000);
  if (!step) return { type: 'wait' };
  return { type: 'move', dx: step.x - p.x, dy: step.y - p.y };
}

export function playRun(seed, maxFloor = 5, maxTicks = 20000) {
  const G = newRun(seed);
  let ticks = 0;
  const stats = { seed, floorsCleared: 0, attempts: [], deaths: 0, status: null, kills: 0 };
  let guard = 0;
  while (ticks < maxTicks && guard++ < 10000) {
    if (G.status === 'won' || G.status === 'over') break;
    if (G.status === 'relic') {
      if (G.floor >= maxFloor) break;
      stats.attempts.push(G.attemptsUsed + 1);
      chooseRelic(G, G.offers[0]);
      continue;
    }
    const a = botAction(G);
    act(G, a);
    ticks++;
    if (G.events.some((e) => e.type === 'loop_lost')) stats.deaths++;
  }
  stats.floorsCleared = G.clearedFloors;
  stats.status = G.status;
  stats.kills = G.kills;
  stats.lastFloor = G.floor;
  return stats;
}

// CLI
if (import.meta.url === `file://${process.argv[1]}`) {
  const runs = Number(process.argv[2] ?? 50);
  const maxFloor = Number(process.argv[3] ?? 5);
  let wins = 0;
  const floorHist = {};
  let deaths = 0;
  const t0 = Date.now();
  for (let i = 0; i < runs; i++) {
    const s = playRun(1000 + i, maxFloor);
    if (s.status === 'won') wins++;
    floorHist[s.lastFloor] = (floorHist[s.lastFloor] || 0) + 1;
    deaths += s.deaths;
  }
  console.log(`runs=${runs} wins=${wins} (${((100 * wins) / runs).toFixed(0)}%) avgDeaths=${(deaths / runs).toFixed(1)} lastFloorHist=${JSON.stringify(floorHist)} ms=${Date.now() - t0}`);
}
