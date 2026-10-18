// Tile grid helpers. Map = { w, h, tiles: number[] } in row-major order.
export const T = { WALL: 0, FLOOR: 1, DOOR: 2, EXIT: 3, PLATE: 4 };

export const DIRS = [
  { dx: 0, dy: -1 },
  { dx: 1, dy: 0 },
  { dx: 0, dy: 1 },
  { dx: -1, dy: 0 },
];

export const inBounds = (m, x, y) => x >= 0 && y >= 0 && x < m.w && y < m.h;
export const tileAt = (m, x, y) => m.tiles[y * m.w + x];
export const setTile = (m, x, y, t) => {
  m.tiles[y * m.w + x] = t;
};

export const manhattan = (ax, ay, bx, by) => Math.abs(ax - bx) + Math.abs(ay - by);

/** Can a unit stand here (ignores units). Closed doors block. */
export function isWalkable(G, x, y) {
  if (!inBounds(G.map, x, y)) return false;
  const t = tileAt(G.map, x, y);
  if (t === T.WALL) return false;
  if (t === T.DOOR) return !!G.door.open;
  return true;
}

/** Blocks line of sight. Closed doors and walls are opaque. */
export function isOpaque(G, x, y) {
  if (!inBounds(G.map, x, y)) return true;
  const t = tileAt(G.map, x, y);
  if (t === T.WALL) return true;
  if (t === T.DOOR) return !G.door.open;
  return false;
}

/** Bresenham line of sight between two tiles; endpoints are not tested. */
export function lineClear(G, x0, y0, x1, y1) {
  const dx = Math.abs(x1 - x0);
  const dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1;
  const sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  let x = x0;
  let y = y0;
  for (let guard = 0; guard < 500; guard++) {
    if (x === x1 && y === y1) return true;
    if (!(x === x0 && y === y0) && isOpaque(G, x, y)) return false;
    const e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y += sy;
    }
  }
  return false;
}
