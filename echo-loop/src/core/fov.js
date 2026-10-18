import { lineClear, inBounds } from './grid.js';

/**
 * Visibility mask for a viewer at (cx, cy) with radius r.
 * Returns Uint8Array(w*h), 1 = visible.
 */
export function computeFov(G, cx, cy, r) {
  const m = G.map;
  const mask = new Uint8Array(m.w * m.h);
  const r2 = r * r + r; // slightly generous circle
  for (let y = cy - r; y <= cy + r; y++) {
    for (let x = cx - r; x <= cx + r; x++) {
      if (!inBounds(m, x, y)) continue;
      const dx = x - cx;
      const dy = y - cy;
      if (dx * dx + dy * dy > r2) continue;
      if (lineClear(G, cx, cy, x, y)) mask[y * m.w + x] = 1;
    }
  }
  mask[cy * m.w + cx] = 1;
  return mask;
}
