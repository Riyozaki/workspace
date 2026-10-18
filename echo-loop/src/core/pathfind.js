import { DIRS, inBounds, isWalkable, tileAt } from './grid.js';

/**
 * BFS over walkable tiles. `blocked(x,y)` marks tiles that cannot be entered
 * (other enemies). The goal tile is always allowed as a destination.
 * Returns the first step {x,y} toward `goal`, or null if unreachable within `maxDist`.
 */
export function nextStep(G, from, goal, blocked, maxDist = 40) {
  if (from.x === goal.x && from.y === goal.y) return null;
  const m = G.map;
  const n = m.w * m.h;
  const prev = new Int32Array(n).fill(-1);
  const dist = new Int32Array(n).fill(-1);
  const startI = from.y * m.w + from.x;
  const goalI = goal.y * m.w + goal.x;
  const queue = [startI];
  dist[startI] = 0;
  prev[startI] = startI;
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    if (cur === goalI) break;
    const cx = cur % m.w;
    const cy = (cur - cx) / m.w;
    if (dist[cur] >= maxDist) continue;
    for (const d of DIRS) {
      const nx = cx + d.dx;
      const ny = cy + d.dy;
      if (!inBounds(m, nx, ny)) continue;
      const ni = ny * m.w + nx;
      if (dist[ni] !== -1) continue;
      if (!isWalkable(G, nx, ny)) continue; // goal must be standable too
      if (ni !== goalI && blocked && blocked(nx, ny)) continue;
      dist[ni] = dist[cur] + 1;
      prev[ni] = cur;
      queue.push(ni);
    }
  }
  if (dist[goalI] === -1) return null;
  // walk back from goal to the tile adjacent to start
  let i = goalI;
  while (prev[i] !== startI) i = prev[i];
  return { x: i % m.w, y: Math.floor(i / m.w) };
}

/** Distances (BFS) from a source over walkable tiles. Unreachable = -1. */
export function distanceMap(G, sx, sy, passable = (x, y) => isWalkable(G, x, y)) {
  const m = G.map;
  const dist = new Int32Array(m.w * m.h).fill(-1);
  const q = [sy * m.w + sx];
  dist[q[0]] = 0;
  for (let h = 0; h < q.length; h++) {
    const cur = q[h];
    const cx = cur % m.w;
    const cy = (cur - cx) / m.w;
    for (const d of DIRS) {
      const nx = cx + d.dx;
      const ny = cy + d.dy;
      if (!inBounds(m, nx, ny)) continue;
      const ni = ny * m.w + nx;
      if (dist[ni] !== -1) continue;
      if (!passable(nx, ny)) continue;
      dist[ni] = dist[cur] + 1;
      q.push(ni);
    }
  }
  return { dist, w: m.w };
}
