// Enemy AI. Every behaviour is driven by what the enemy can see (LOS + sight radius),
// its memory of the last seen position (alert timer), and noise from player attacks.
import { DIRS, isWalkable, lineClear, manhattan, inBounds, tileAt, T } from './grid.js';
import { nextStep } from './pathfind.js';
import { rnd, rint } from './rng.js';
import { ENEMY_DEFS } from './entities.js';

export const ALERT_TURNS = 6;

/** Living units that enemies can hit: player (if alive) and echoes. */
export function targetsOf(G) {
  const list = [];
  if (G.player.hp > 0) list.push({ kind: 'player', x: G.player.x, y: G.player.y, ref: G.player });
  for (const e of G.echoes) if (e.hp > 0) list.push({ kind: 'echo', x: e.x, y: e.y, ref: e });
  return list;
}

export function enemyAt(G, x, y) {
  return G.enemies.find((e) => e.hp > 0 && e.x === x && e.y === y) || null;
}

export function unitAt(G, x, y) {
  if (G.player.hp > 0 && G.player.x === x && G.player.y === y) return { kind: 'player', ref: G.player };
  const ech = G.echoes.find((e) => e.hp > 0 && e.x === x && e.y === y);
  return ech ? { kind: 'echo', ref: ech } : null;
}

/** Enemy takes damage from a player or echo, handled by the engine. */
function hitUnit(G, target, dmg, ev, source) {
  if (target.kind === 'player') {
    G.player.hp -= dmg;
    ev.push({ type: 'hit', target: 'player', x: target.ref.x, y: target.ref.y, amount: dmg, by: source });
  } else {
    target.ref.hp = 0; // echo dies on any hit
    ev.push({ type: 'echo_lost', x: target.ref.x, y: target.ref.y, by: source });
  }
}

function wander(G, e) {
  if (rnd(G.rng) < 0.5) return;
  const opts = DIRS.filter((d) => {
    const nx = e.x + d.dx;
    const ny = e.y + d.dy;
    return isWalkable(G, nx, ny) && !enemyAt(G, nx, ny) && !unitAt(G, nx, ny) && tileAt(G.map, nx, ny) !== T.PLATE;
  });
  if (!opts.length) return;
  const d = opts[rint(G.rng, opts.length)];
  moveEnemy(G, e, e.x + d.dx, e.y + d.dy);
}

function moveEnemy(G, e, nx, ny) {
  const from = { x: e.x, y: e.y };
  e.x = nx;
  e.y = ny;
  G.events.push({ type: 'move', unit: 'enemy', id: e.id, from, to: { x: nx, y: ny } });
}

/** Move one step toward goal or attack the unit standing on the next step. */
function stepToward(G, e, goal, ev) {
  const step = nextStep(G, e, goal, (x, y) => !!enemyAt(G, x, y), 60);
  if (!step) return false;
  const u = unitAt(G, step.x, step.y);
  if (u) {
    hitUnit(G, u, ENEMY_DEFS[e.type].dmg, ev, e.type);
    return true;
  }
  if (enemyAt(G, step.x, step.y)) return false;
  moveEnemy(G, e, step.x, step.y);
  return true;
}

function nearestVisible(G, e) {
  let best = null;
  let bestD = Infinity;
  for (const t of targetsOf(G)) {
    const d = manhattan(e.x, e.y, t.x, t.y);
    if (d > ENEMY_DEFS[e.type].sight) continue;
    if (!lineClear(G, e.x, e.y, t.x, t.y)) continue;
    if (d < bestD) {
      bestD = d;
      best = t;
    }
  }
  return best;
}

/** Run one enemy's turn. Mutates G (positions, player.hp, echoes). */
export function enemyTurn(G, e, ev) {
  if (e.hp <= 0) return;
  const def = ENEMY_DEFS[e.type];
  const seen = nearestVisible(G, e);

  // --- perception & memory ---
  if (seen) {
    e.state = 'chase';
    e.lastSeen = { x: seen.x, y: seen.y };
    e.alert = ALERT_TURNS;
  } else if (e.state === 'chase') {
    e.state = 'alert';
    e.alert = ALERT_TURNS;
  } else if (e.state === 'alert') {
    e.alert--;
    if (e.alert <= 0) e.state = 'patrol';
  }
  const memory = e.state !== 'patrol' && e.lastSeen ? e.lastSeen : null;

  switch (e.type) {
    case 'husk':
    case 'warden': {
      if (e.type === 'warden') {
        e.summonCd = (e.summonCd ?? 4) - 1;
        if (e.summonCd <= 0 && (seen || memory)) {
          e.summonCd = 4;
          summonHusk(G, e, ev);
        }
      }
      if (seen && manhattan(e.x, e.y, seen.x, seen.y) === 1) {
        hitUnit(G, seen, def.dmg, ev, e.type);
        return;
      }
      const goal = seen ? { x: seen.x, y: seen.y } : memory;
      if (goal) {
        if (!stepToward(G, e, goal, ev)) wander(G, e);
      } else wander(G, e);
      return;
    }
    case 'sniper': {
      if (seen) {
        const dx = Math.abs(seen.x - e.x);
        const dy = Math.abs(seen.y - e.y);
        const aligned = dx === 0 || dy === 0;
        const d = dx + dy;
        if (aligned && d <= 5) {
          hitUnit(G, seen, def.dmg, ev, 'sniper');
          ev.push({ type: 'shot', from: { x: e.x, y: e.y }, to: { x: seen.x, y: seen.y } });
          return;
        }
        if (d <= 2) {
          // keep distance: step to the free neighbour farthest from the target
          let best = null;
          let bestD = d;
          for (const dd of DIRS) {
            const nx = e.x + dd.dx;
            const ny = e.y + dd.dy;
            if (!isWalkable(G, nx, ny) || enemyAt(G, nx, ny) || unitAt(G, nx, ny)) continue;
            const nd = manhattan(nx, ny, seen.x, seen.y);
            if (nd > bestD) {
              bestD = nd;
              best = { x: nx, y: ny };
            }
          }
          if (best) moveEnemy(G, e, best.x, best.y);
          return;
        }
        if (d > 4) stepToward(G, e, { x: seen.x, y: seen.y }, ev);
        return;
      }
      if (memory) stepToward(G, e, memory, ev);
      else wander(G, e);
      return;
    }
    case 'charger': {
      if (e.wind) {
        // telegraphed charge: fixed direction, up to 4 tiles, hits first unit
        const dir = e.wind;
        e.wind = null;
        let cx = e.x;
        let cy = e.y;
        for (let k = 0; k < 4; k++) {
          const nx = cx + dir.dx;
          const ny = cy + dir.dy;
          if (!isWalkable(G, nx, ny) || enemyAt(G, nx, ny)) break;
          const u = unitAt(G, nx, ny);
          if (u) {
            hitUnit(G, u, def.dmg, ev, 'charger');
            ev.push({ type: 'charge', from: { x: e.x, y: e.y }, to: { x: nx, y: ny } });
            break;
          }
          cx = nx;
          cy = ny;
        }
        if (cx !== e.x || cy !== e.y) moveEnemy(G, e, cx, cy);
        return;
      }
      if (seen) {
        const dx = seen.x - e.x;
        const dy = seen.y - e.y;
        const d = Math.abs(dx) + Math.abs(dy);
        const aligned = dx === 0 || dy === 0;
        if (aligned && d >= 2 && d <= 4) {
          e.wind = { dx: Math.sign(dx), dy: Math.sign(dy) };
          ev.push({ type: 'windup', id: e.id, x: e.x, y: e.y, dir: e.wind });
          return;
        }
        stepToward(G, e, { x: seen.x, y: seen.y }, ev);
        return;
      }
      if (memory) stepToward(G, e, memory, ev);
      else wander(G, e);
      return;
    }
    default:
      return;
  }
}

function summonHusk(G, boss, ev) {
  const husks = G.enemies.filter((e) => e.hp > 0 && e.type === 'husk').length;
  if (husks >= 6) return;
  for (const d of DIRS) {
    const nx = boss.x + d.dx;
    const ny = boss.y + d.dy;
    if (isWalkable(G, nx, ny) && !enemyAt(G, nx, ny) && !unitAt(G, nx, ny)) {
      const id = G.nextId++;
      G.enemies.push(newEnemy(id, 'husk', nx, ny));
      ev.push({ type: 'summon', x: nx, y: ny });
      return;
    }
  }
}

export function newEnemy(id, type, x, y) {
  const def = ENEMY_DEFS[type];
  return { id, type, x, y, hp: def.hp, maxHp: def.hp, state: 'patrol', lastSeen: null, alert: 0, wind: null, summonCd: 4 };
}

export { inBounds };
