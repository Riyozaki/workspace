// Procedural sprites drawn with canvas primitives. No external image assets.
// All functions draw centred on (cx, cy) inside a tile of size s (pixels).

const hash = (x, y) => {
  let h = (x * 374761393 + y * 668265263) ^ 0x5bd1e995;
  h = (h ^ (h >>> 13)) * 1274126177;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};

export function tileHash(x, y) {
  return hash(x, y);
}

export function drawWallTile(ctx, px, py, s, x, y, faceFloorBelow) {
  const h = hash(x, y);
  ctx.fillStyle = h > 0.5 ? '#1f1d29' : '#211f2c';
  ctx.fillRect(px, py, s, s);
  // block seams
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.fillRect(px, py + s * 0.5, s, 1.5);
  ctx.fillRect(px + (h > 0.5 ? s * 0.5 : s * 0.25), py, 1.5, s * 0.5);
  ctx.fillRect(px + (h > 0.5 ? s * 0.25 : s * 0.6), py + s * 0.5, 1.5, s * 0.5);
  // top highlight
  ctx.fillStyle = 'rgba(160,150,200,0.07)';
  ctx.fillRect(px, py, s, 2);
  if (faceFloorBelow) {
    // visible wall face: lighter band at the bottom
    const g = ctx.createLinearGradient(0, py + s - 9, 0, py + s);
    g.addColorStop(0, '#3b3751');
    g.addColorStop(1, '#2a2740');
    ctx.fillStyle = g;
    ctx.fillRect(px, py + s - 9, s, 9);
  }
}

export function drawFloorTile(ctx, px, py, s, x, y) {
  const h = hash(x, y);
  ctx.fillStyle = (x + y) % 2 === 0 ? '#2a2935' : '#282733';
  ctx.fillRect(px, py, s, s);
  if (h > 0.72) {
    ctx.fillStyle = 'rgba(0,0,0,0.18)';
    ctx.beginPath();
    ctx.arc(px + s * (0.2 + h * 0.6), py + s * (0.3 + (h - 0.7) * 2), s * 0.09, 0, Math.PI * 2);
    ctx.fill();
  }
  if (h < 0.12) {
    ctx.strokeStyle = 'rgba(0,0,0,0.25)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(px + s * 0.1, py + s * 0.8);
    ctx.lineTo(px + s * 0.45, py + s * 0.55);
    ctx.lineTo(px + s * 0.9, py + s * 0.6);
    ctx.stroke();
  }
}

export function drawDoor(ctx, px, py, s, open) {
  if (open) {
    ctx.fillStyle = 'rgba(120,200,255,0.12)';
    ctx.fillRect(px, py, s, s);
    ctx.strokeStyle = 'rgba(120,200,255,0.6)';
    ctx.lineWidth = 2;
    ctx.strokeRect(px + 4, py + 2, s - 8, s - 4);
    return;
  }
  ctx.fillStyle = '#4a2f22';
  ctx.fillRect(px + 2, py + 1, s - 4, s - 2);
  ctx.fillStyle = '#6b4530';
  for (let i = 0; i < 4; i++) ctx.fillRect(px + 4 + i * ((s - 8) / 4), py + 2, (s - 8) / 8, s - 4);
  ctx.fillStyle = '#8d8d9a';
  ctx.fillRect(px + 2, py + s * 0.3, s - 4, 3);
  ctx.fillRect(px + 2, py + s * 0.66, s - 4, 3);
  ctx.beginPath();
  ctx.arc(px + s * 0.7, py + s * 0.5, 2.5, 0, Math.PI * 2);
  ctx.fill();
}

export function drawPlate(ctx, px, py, s, pressed, t) {
  const cx = px + s / 2;
  const cy = py + s / 2;
  ctx.fillStyle = '#34303f';
  ctx.beginPath();
  ctx.arc(cx, cy, s * 0.4, 0, Math.PI * 2);
  ctx.fill();
  const glow = pressed ? 0.9 : 0.35 + 0.15 * Math.sin(t * 3);
  ctx.strokeStyle = pressed ? `rgba(120,255,200,${glow})` : `rgba(255,190,90,${glow})`;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, s * 0.28, 0, Math.PI * 2);
  ctx.stroke();
  for (let i = 0; i < 4; i++) {
    const a = i * (Math.PI / 2) + t * (pressed ? 0 : 0.6);
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * s * 0.12, cy + Math.sin(a) * s * 0.12);
    ctx.lineTo(cx + Math.cos(a) * s * 0.22, cy + Math.sin(a) * s * 0.22);
    ctx.stroke();
  }
}

export function drawExit(ctx, px, py, s, t) {
  const cx = px + s / 2;
  const cy = py + s / 2;
  const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, s * 0.6);
  g.addColorStop(0, 'rgba(180,120,255,0.55)');
  g.addColorStop(1, 'rgba(180,120,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(px - s * 0.2, py - s * 0.2, s * 1.4, s * 1.4);
  for (let k = 0; k < 3; k++) {
    ctx.strokeStyle = `rgba(${200 - k * 30},${140 + k * 30},255,${0.85 - k * 0.2})`;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.arc(cx, cy, s * (0.12 + k * 0.1), t * (2 + k) + k, t * (2 + k) + k + Math.PI * 1.4);
    ctx.stroke();
  }
}

/** Player: hooded wanderer with a lantern. ghost=true renders the echo variant. */
export function drawPlayer(ctx, cx, cy, s, opts = {}) {
  const { ghost = false, t = 0, lantern = true, hurt = 0 } = opts;
  ctx.save();
  if (ghost) ctx.globalAlpha = 0.55 + 0.1 * Math.sin(t * 4);
  const cloak = ghost ? '#2d6f9e' : hurt > 0 ? '#8a3b52' : '#4a3a7a';
  const hood = ghost ? '#4aa3d6' : '#6a58a6';
  // cloak with wavy hem
  ctx.fillStyle = cloak;
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.26, cy + s * 0.34);
  ctx.quadraticCurveTo(cx - s * 0.2, cy - s * 0.02, cx - s * 0.12, cy - s * 0.12);
  ctx.lineTo(cx + s * 0.12, cy - s * 0.12);
  ctx.quadraticCurveTo(cx + s * 0.2, cy - s * 0.02, cx + s * 0.26, cy + s * 0.34);
  for (let i = 0; i < 4; i++) {
    const x0 = cx + s * (0.26 - i * 0.13);
    const wob = Math.sin(t * 6 + i) * s * 0.03;
    ctx.lineTo(x0 - s * 0.065, cy + s * 0.27 + wob);
    ctx.lineTo(x0 - s * 0.13, cy + s * 0.34);
  }
  ctx.closePath();
  ctx.fill();
  // hood
  ctx.fillStyle = hood;
  ctx.beginPath();
  ctx.arc(cx, cy - s * 0.12, s * 0.15, 0, Math.PI * 2);
  ctx.fill();
  // face shadow + eyes
  ctx.fillStyle = '#120d1f';
  ctx.beginPath();
  ctx.ellipse(cx, cy - s * 0.1, s * 0.1, s * 0.08, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = ghost ? '#c7f4ff' : '#ffd166';
  ctx.fillRect(cx - s * 0.06, cy - s * 0.12, s * 0.03, s * 0.03);
  ctx.fillRect(cx + s * 0.03, cy - s * 0.12, s * 0.03, s * 0.03);
  if (lantern && !ghost) {
    ctx.fillStyle = '#c9a24a';
    ctx.fillRect(cx + s * 0.2, cy + s * 0.02, s * 0.06, s * 0.1);
    ctx.fillStyle = '#ffe08a';
    ctx.beginPath();
    ctx.arc(cx + s * 0.23, cy + s * 0.0, s * 0.05, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

export function drawHusk(ctx, cx, cy, s, t) {
  ctx.fillStyle = '#5d7a52';
  ctx.beginPath();
  ctx.ellipse(cx, cy + s * 0.05, s * 0.24, s * 0.28, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#4a6443';
  ctx.beginPath();
  ctx.arc(cx, cy - s * 0.2, s * 0.17, 0, Math.PI * 2);
  ctx.fill();
  // outstretched arms
  ctx.strokeStyle = '#5d7a52';
  ctx.lineWidth = s * 0.07;
  const sway = Math.sin(t * 5) * s * 0.03;
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.2, cy - s * 0.02);
  ctx.lineTo(cx - s * 0.38, cy + s * 0.05 + sway);
  ctx.moveTo(cx + s * 0.2, cy - s * 0.02);
  ctx.lineTo(cx + s * 0.38, cy + s * 0.05 - sway);
  ctx.stroke();
  // red eyes
  ctx.fillStyle = '#ff4d4d';
  ctx.fillRect(cx - s * 0.1, cy - s * 0.23, s * 0.06, s * 0.05);
  ctx.fillRect(cx + s * 0.04, cy - s * 0.23, s * 0.06, s * 0.05);
  // tattered hem
  ctx.fillStyle = '#3b4d37';
  for (let i = 0; i < 3; i++) ctx.fillRect(cx - s * 0.2 + i * s * 0.13, cy + s * 0.27, s * 0.07, s * 0.07);
}

export function drawSniper(ctx, cx, cy, s, t) {
  ctx.fillStyle = '#6b3d7a';
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.24, cy + s * 0.36);
  ctx.lineTo(cx - s * 0.14, cy - s * 0.1);
  ctx.lineTo(cx + s * 0.14, cy - s * 0.1);
  ctx.lineTo(cx + s * 0.24, cy + s * 0.36);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = '#d7b9a0';
  ctx.beginPath();
  ctx.arc(cx, cy - s * 0.2, s * 0.13, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#3a2250';
  ctx.beginPath();
  ctx.arc(cx, cy - s * 0.25, s * 0.14, Math.PI, 0);
  ctx.fill();
  // crossbow
  ctx.strokeStyle = '#c9a24a';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx + s * 0.28, cy - s * 0.12);
  ctx.quadraticCurveTo(cx + s * 0.36, cy + s * 0.05, cx + s * 0.26, cy + s * 0.2);
  ctx.moveTo(cx + s * 0.28, cy - s * 0.12);
  ctx.lineTo(cx + s * 0.22, cy + s * 0.18);
  ctx.stroke();
  // glint
  ctx.fillStyle = `rgba(255,220,120,${0.4 + 0.4 * Math.sin(t * 8)})`;
  ctx.fillRect(cx + s * 0.22, cy - s * 0.23, 2, 2);
}

export function drawCharger(ctx, cx, cy, s, t, windDir) {
  ctx.fillStyle = windDir ? '#c0392b' : '#8e3b2e';
  ctx.beginPath();
  ctx.ellipse(cx, cy + s * 0.04, s * 0.32, s * 0.26, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#e8d9b5';
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.2, cy - s * 0.12);
  ctx.lineTo(cx - s * 0.3, cy - s * 0.38);
  ctx.lineTo(cx - s * 0.08, cy - s * 0.18);
  ctx.moveTo(cx + s * 0.2, cy - s * 0.12);
  ctx.lineTo(cx + s * 0.3, cy - s * 0.38);
  ctx.lineTo(cx + s * 0.08, cy - s * 0.18);
  ctx.fill();
  ctx.fillStyle = '#ffe066';
  ctx.fillRect(cx - s * 0.14, cy - s * 0.06, s * 0.08, s * 0.06);
  ctx.fillRect(cx + s * 0.06, cy - s * 0.06, s * 0.08, s * 0.06);
  // legs
  ctx.fillStyle = '#5a2019';
  const k = Math.sin(t * 10) * s * 0.03;
  ctx.fillRect(cx - s * 0.2, cy + s * 0.22 + k, s * 0.08, s * 0.1);
  ctx.fillRect(cx + s * 0.12, cy + s * 0.22 - k, s * 0.08, s * 0.1);
}

export function drawWarden(ctx, cx, cy, s, t) {
  const big = s * 1.5;
  ctx.fillStyle = '#2a1f35';
  ctx.beginPath();
  ctx.moveTo(cx - big * 0.36, cy + big * 0.4);
  ctx.lineTo(cx - big * 0.28, cy - big * 0.1);
  ctx.lineTo(cx - big * 0.14, cy - big * 0.3);
  ctx.lineTo(cx + big * 0.14, cy - big * 0.3);
  ctx.lineTo(cx + big * 0.28, cy - big * 0.1);
  ctx.lineTo(cx + big * 0.36, cy + big * 0.4);
  ctx.closePath();
  ctx.fill();
  // crown spikes
  ctx.fillStyle = '#9d5cff';
  for (let i = -2; i <= 2; i++) {
    ctx.beginPath();
    ctx.moveTo(cx + i * big * 0.1 - big * 0.04, cy - big * 0.3);
    ctx.lineTo(cx + i * big * 0.1, cy - big * 0.5 - (i === 0 ? big * 0.06 : 0));
    ctx.lineTo(cx + i * big * 0.1 + big * 0.04, cy - big * 0.3);
    ctx.fill();
  }
  // core glow
  const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, big * 0.35);
  g.addColorStop(0, `rgba(190,120,255,${0.8 + 0.2 * Math.sin(t * 4)})`);
  g.addColorStop(1, 'rgba(190,120,255,0)');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(cx, cy, big * 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.fillRect(cx - big * 0.1, cy - big * 0.04, big * 0.06, big * 0.05);
  ctx.fillRect(cx + big * 0.05, cy - big * 0.04, big * 0.06, big * 0.05);
}

export function drawPotion(ctx, cx, cy, s, t) {
  const bob = Math.sin(t * 3) * s * 0.03;
  ctx.fillStyle = '#c0392b';
  ctx.beginPath();
  ctx.arc(cx, cy + s * 0.08 + bob, s * 0.17, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#e9e4f5';
  ctx.fillRect(cx - s * 0.05, cy - s * 0.2 + bob, s * 0.1, s * 0.1);
  ctx.fillStyle = '#7a4a2a';
  ctx.fillRect(cx - s * 0.06, cy - s * 0.27 + bob, s * 0.12, s * 0.07);
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.fillRect(cx - s * 0.1, cy + s * 0.02 + bob, s * 0.04, s * 0.1);
}

export function drawShard(ctx, cx, cy, s, t) {
  const bob = Math.sin(t * 2.5) * s * 0.04;
  const g = ctx.createRadialGradient(cx, cy + bob, 1, cx, cy + bob, s * 0.5);
  g.addColorStop(0, 'rgba(120,230,255,0.6)');
  g.addColorStop(1, 'rgba(120,230,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(cx - s * 0.5, cy - s * 0.5, s, s);
  ctx.fillStyle = '#7fe8ff';
  ctx.beginPath();
  ctx.moveTo(cx, cy - s * 0.25 + bob);
  ctx.lineTo(cx + s * 0.18, cy + bob);
  ctx.lineTo(cx, cy + s * 0.25 + bob);
  ctx.lineTo(cx - s * 0.18, cy + bob);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = '#d9faff';
  ctx.beginPath();
  ctx.moveTo(cx, cy - s * 0.25 + bob);
  ctx.lineTo(cx + s * 0.06, cy - s * 0.05 + bob);
  ctx.lineTo(cx - s * 0.06, cy - s * 0.05 + bob);
  ctx.fill();
}
