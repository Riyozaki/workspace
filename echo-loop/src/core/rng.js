// Deterministic PRNG (mulberry32-style). State is a plain object {s} so it can be
// structuredClone'd together with the game state (needed for rewind).
export function makeRng(seed) {
  return { s: seed >>> 0 };
}

/** Float in [0, 1). Mutates r.s. */
export function rnd(r) {
  r.s = (r.s + 0x6d2b79f5) >>> 0;
  let t = r.s;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

/** Integer in [0, n). */
export function rint(r, n) {
  return Math.floor(rnd(r) * n);
}

/** Integer in [a, b] inclusive. */
export function rrange(r, a, b) {
  return a + Math.floor(rnd(r) * (b - a + 1));
}

export function rpick(r, arr) {
  return arr[Math.floor(rnd(r) * arr.length)];
}

/** Fisher-Yates shuffle, returns a new array. */
export function rshuffle(r, arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rnd(r) * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
