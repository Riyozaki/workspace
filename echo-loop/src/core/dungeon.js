// Procedural floor generation. Pure function of (seed, floor).
import { makeRng, rint, rrange, rpick, rshuffle, rnd } from './rng.js';
import { T, DIRS, inBounds, tileAt, setTile, manhattan } from './grid.js';
import { distanceMap } from './pathfind.js';

export const MAP_W = 60;
export const MAP_H = 38;

/**
 * Returns { map, rooms, start, exit, gate:{x,y}|null, plate:{x,y}|null, enemies:[{type,x,y}], items:[{type,x,y}] }
 * Guarantees: exit reachable from start; if a gate exists, exit is NOT reachable with the gate closed
 * (the gate is mandatory) and the plate is reachable from start without passing the gate.
 */
export function generateFloor(seed, floor) {
  for (let attempt = 0; attempt < 50; attempt++) {
    const r = makeRng(seed + attempt * 977);
    const f = tryGenerate(r, floor);
    if (f) return f;
  }
  throw new Error('floor generation failed for seed ' + seed);
}

function tryGenerate(r, floor) {
  const map = { w: MAP_W, h: MAP_H, tiles: new Array(MAP_W * MAP_H).fill(T.WALL) };

  // --- BSP split ---
  const leaves = [];
  split(r, { x: 1, y: 1, w: MAP_W - 2, h: MAP_H - 2 }, 0, leaves);

  // --- rooms inside leaves ---
  const rooms = [];
  for (const L of leaves) {
    const rw = rrange(r, Math.min(4, L.w - 2), Math.max(4, L.w - 2));
    const rh = rrange(r, Math.min(4, L.h - 2), Math.max(4, L.h - 2));
    const rx = L.x + 1 + rint(r, Math.max(1, L.w - rw - 1));
    const ry = L.y + 1 + rint(r, Math.max(1, L.h - rh - 1));
    const room = { x: rx, y: ry, w: Math.min(rw, L.w - 2), h: Math.min(rh, L.h - 2) };
    rooms.push(room);
    for (let y = room.y; y < room.y + room.h; y++)
      for (let x = room.x; x < room.x + room.w; x++) setTile(map, x, y, T.FLOOR);
  }

  // --- corridors: chain rooms in order, plus some loops ---
  const center = (rm) => ({ x: rm.x + (rm.w >> 1), y: rm.y + (rm.h >> 1) });
  for (let i = 0; i + 1 < rooms.length; i++) carveL(r, map, center(rooms[i]), center(rooms[i + 1]));
  for (let i = 0; i + 2 < rooms.length; i++) {
    if (rnd(r) < 0.3) carveL(r, map, center(rooms[i]), center(rooms[i + 2]));
  }

  const start = center(rooms[0]);

  // --- exit = farthest room centre by walking distance ---
  const dStart = distanceMap({ map }, start.x, start.y, (x, y) => tileAt(map, x, y) !== T.WALL);
  let exit = null;
  let bestD = -1;
  for (let i = 1; i < rooms.length; i++) {
    const c = center(rooms[i]);
    const d = dStart.dist[c.y * MAP_W + c.x];
    if (d > bestD) {
      bestD = d;
      exit = c;
    }
  }
  if (!exit || bestD < 20) return null;
  setTile(map, exit.x, exit.y, T.EXIT);

  // --- gate: a corridor tile on the start->exit path that is mandatory ---
  let gate = null;
  let plate = null;
  if (floor >= 2) {
    const path = shortestPath(map, start, exit);
    const cands = [];
    for (let i = Math.floor(path.length * 0.3); i < Math.floor(path.length * 0.75); i++) {
      const p = path[i];
      if (isCorridor(map, p.x, p.y)) cands.push(p);
    }
    for (const c of rshuffle(r, cands)) {
      setTile(map, c.x, c.y, T.DOOR);
      const reach = distanceMap({ map }, start.x, start.y, (x, y) => tileAt(map, x, y) !== T.WALL && tileAt(map, x, y) !== T.DOOR);
      if (reach.dist[exit.y * MAP_W + exit.x] === -1) {
        // mandatory gate found; now pick plate on the start side, close to the gate
        const near = distanceMap({ map }, c.x, c.y, (x, y) => tileAt(map, x, y) !== T.WALL && tileAt(map, x, y) !== T.DOOR);
        const pc = [];
        for (let y = 1; y < MAP_H - 1; y++)
          for (let x = 1; x < MAP_W - 1; x++) {
            const t = tileAt(map, x, y);
            if (t !== T.FLOOR || !isRoomTile(map, x, y)) continue;
            const dd = near.dist[y * MAP_W + x];
            const ds = reach.dist[y * MAP_W + x];
            if (dd >= 2 && dd <= 4 && ds >= 3) pc.push({ x, y });
          }
        if (pc.length) {
          gate = c;
          plate = rpick(r, pc);
          setTile(map, plate.x, plate.y, T.PLATE);
          break;
        }
      }
      setTile(map, c.x, c.y, T.FLOOR);
    }
    if (!gate) return null; // try another layout
  }

  // --- spawn enemies ---
  const special = new Set([`${start.x},${start.y}`, `${exit.x},${exit.y}`]);
  const enemies = [];
  const roomPool = rooms.slice(1).filter((rm) => !(exit.x >= rm.x && exit.x < rm.x + rm.w && exit.y >= rm.y && exit.y < rm.y + rm.h));
  const weights = [['husk', 5]];
  if (floor >= 2) weights.push(['sniper', 2]);
  if (floor >= 3) weights.push(['charger', 2]);
  const total = weights.reduce((s, [, w]) => s + w, 0);
  const count = 3 + floor * 2;
  const occupied = new Set(special);
  if (plate) occupied.add(`${plate.x},${plate.y}`);
  if (gate) occupied.add(`${gate.x},${gate.y}`);
  const placeIn = (rm, minDistStart) => {
    for (let tries = 0; tries < 60; tries++) {
      const x = rrange(r, rm.x, rm.x + rm.w - 1);
      const y = rrange(r, rm.y, rm.y + rm.h - 1);
      const k = `${x},${y}`;
      if (occupied.has(k) || tileAt(map, x, y) !== T.FLOOR) continue;
      if (manhattan(x, y, start.x, start.y) < minDistStart) continue;
      occupied.add(k);
      return { x, y };
    }
    return null;
  };
  for (let i = 0; i < count; i++) {
    const rm = roomPool[i % roomPool.length];
    const p = placeIn(rm, 7);
    if (!p) continue;
    let roll = rnd(r) * total;
    let type = weights[0][0];
    for (const [t, w] of weights) {
      if (roll < w) {
        type = t;
        break;
      }
      roll -= w;
    }
    enemies.push({ type, x: p.x, y: p.y });
  }
  if (floor === 5) {
    // boss guards the exit
    const ex = exit;
    for (const d of DIRS) {
      const bx = ex.x + d.dx * 2;
      const by = ex.y + d.dy * 2;
      if (inBounds(map, bx, by) && tileAt(map, bx, by) === T.FLOOR && !occupied.has(`${bx},${by}`)) {
        enemies.push({ type: 'warden', x: bx, y: by });
        occupied.add(`${bx},${by}`);
        break;
      }
    }
  }

  // --- items: potions + one rewind shard ---
  const items = [];
  const potions = floor >= 3 ? 3 : 2;
  for (let i = 0; i < potions; i++) {
    const p = placeIn(rpick(r, roomPool), 4);
    if (p) items.push({ type: 'potion', x: p.x, y: p.y });
  }
  const sp = placeIn(rpick(r, roomPool), 4);
  if (sp) items.push({ type: 'shard', x: sp.x, y: sp.y });

  return { map, rooms, start, exit, gate, plate, enemies, items };
}

function split(r, rect, depth, out) {
  const canV = rect.w >= 16;
  const canH = rect.h >= 12;
  if (depth >= 4 || (!canV && !canH) || (rect.w < 22 && rect.h < 16 && depth >= 2)) {
    out.push(rect);
    return;
  }
  let vertical;
  if (canV && canH) vertical = rect.w > rect.h * 1.25 ? true : rect.h > rect.w * 1.25 ? false : rnd(r) < 0.5;
  else vertical = canV;
  if (vertical) {
    const cut = rrange(r, Math.floor(rect.w * 0.4), Math.floor(rect.w * 0.6));
    split(r, { x: rect.x, y: rect.y, w: cut, h: rect.h }, depth + 1, out);
    split(r, { x: rect.x + cut, y: rect.y, w: rect.w - cut, h: rect.h }, depth + 1, out);
  } else {
    const cut = rrange(r, Math.floor(rect.h * 0.4), Math.floor(rect.h * 0.6));
    split(r, { x: rect.x, y: rect.y, w: rect.w, h: cut }, depth + 1, out);
    split(r, { x: rect.x, y: rect.y + cut, w: rect.w, h: rect.h - cut }, depth + 1, out);
  }
}

function carveL(r, map, a, b) {
  const horizFirst = rnd(r) < 0.5;
  const corner = horizFirst ? { x: b.x, y: a.y } : { x: a.x, y: b.y };
  carveLine(map, a, corner);
  carveLine(map, corner, b);
}

function carveLine(map, a, b) {
  let x = a.x;
  let y = a.y;
  for (let i = 0; i < 400; i++) {
    if (tileAt(map, x, y) === T.WALL) setTile(map, x, y, T.FLOOR);
    if (x === b.x && y === b.y) break;
    if (x !== b.x) x += Math.sign(b.x - x);
    else y += Math.sign(b.y - y);
  }
}

function isCorridor(map, x, y) {
  const open = (dx, dy) => {
    const t = tileAt(map, x + dx, y + dy);
    return t !== undefined && t !== T.WALL;
  };
  const h = open(-1, 0) && open(1, 0) && !open(0, -1) && !open(0, 1);
  const v = open(0, -1) && open(0, 1) && !open(-1, 0) && !open(1, 0);
  return h || v;
}

/** A tile belongs to a room if it has at least 3 floor-ish neighbours in a 3x3 block. */
function isRoomTile(map, x, y) {
  let n = 0;
  for (let dy = -1; dy <= 1; dy++)
    for (let dx = -1; dx <= 1; dx++) {
      const t = tileAt(map, x + dx, y + dy);
      if (t !== undefined && t !== T.WALL) n++;
    }
  return n >= 8;
}

function shortestPath(map, a, b) {
  const { dist } = distanceMap({ map }, a.x, a.y, (x, y) => tileAt(map, x, y) !== T.WALL);
  const path = [];
  let x = b.x;
  let y = b.y;
  let d = dist[y * MAP_W + x];
  while (d > 0) {
    path.push({ x, y });
    for (const dd of DIRS) {
      const nx = x + dd.dx;
      const ny = y + dd.dy;
      if (inBounds(map, nx, ny) && dist[ny * MAP_W + nx] === d - 1) {
        x = nx;
        y = ny;
        break;
      }
    }
    d--;
  }
  path.reverse();
  return path; // excludes start, includes exit
}
