// Canvas renderer. Reads game state (G) and a separate view state (animations, particles).
import { T, inBounds } from '../core/grid.js';
import { computeFov } from '../core/fov.js';
import { modsOf } from '../core/entities.js';
import * as S from './sprites.js';

export const TILE = 40;
const MOVE_ANIM = 0.12; // seconds for a one-tile slide

export function createView() {
  return {
    t: 0,
    anims: new Map(), // unitKey -> {fx,fy,tx,ty,t0}
    particles: [],
    texts: [],
    beams: [], // {x0,y0,x1,y1,color,life,max}
    rings: [],
    shake: 0,
    hurt: 0,
    camX: null,
    camY: null,
    visible: null,
  };
}

/** Feed engine events into the view (animations, particles, texts). */
export function consumeEvents(view, G, events) {
  for (const ev of events) {
    switch (ev.type) {
      case 'move': {
        const key = ev.unit === 'player' ? 'p' : ev.unit === 'echo' ? 'e' + ev.id : 'm' + ev.id;
        view.anims.set(key, { fx: ev.from.x, fy: ev.from.y, tx: ev.to.x, ty: ev.to.y, t0: view.t });
        break;
      }
      case 'hit': {
        const col = ev.target === 'player' ? '#ff6b6b' : '#ffffff';
        view.texts.push({ x: ev.x, y: ev.y, text: `-${ev.amount}`, color: col, life: 0.9, max: 0.9 });
        burst(view, ev.x, ev.y, ev.target === 'player' ? '#ff5555' : '#ffd166', 10);
        if (ev.target === 'player') {
          view.hurt = 0.35;
          view.shake = 0.3;
        }
        break;
      }
      case 'echo_lost':
        burst(view, ev.x, ev.y, '#66ccff', 16);
        view.texts.push({ x: ev.x, y: ev.y, text: 'ECHO LOST', color: '#66ccff', life: 1.1, max: 1.1 });
        break;
      case 'death':
        burst(view, ev.x, ev.y, '#c8a2ff', 22);
        break;
      case 'heal':
        burst(view, ev.x, ev.y, '#7dff9a', 14);
        view.texts.push({ x: ev.x, y: ev.y, text: `+${ev.amount}`, color: '#7dff9a', life: 0.9, max: 0.9 });
        break;
      case 'plate':
        view.rings.push({ x: ev.x, y: ev.y, life: 0.6, max: 0.6, color: '#78ffc8' });
        break;
      case 'pickup':
        burst(view, ev.x, ev.y, ev.item === 'shard' ? '#7fe8ff' : '#ff8080', 12);
        break;
      case 'shot':
        view.beams.push({ x0: ev.from.x, y0: ev.from.y, x1: ev.to.x, y1: ev.to.y, color: '#ffd166', life: 0.25, max: 0.25 });
        break;
      case 'charge':
        view.beams.push({ x0: ev.from.x, y0: ev.from.y, x1: ev.to.x, y1: ev.to.y, color: '#ff5a3c', life: 0.3, max: 0.3 });
        view.shake = Math.max(view.shake, 0.15);
        break;
      case 'exit':
        for (let i = 0; i < 40; i++) burst(view, ev.x, ev.y, i % 2 ? '#c49bff' : '#ffffff', 1);
        break;
      case 'loop_lost':
        view.shake = 0.6;
        for (let i = 0; i < 50; i++) burst(view, G.player.x, G.player.y, i % 3 ? '#8a6bff' : '#66ccff', 1);
        break;
      case 'summon':
        burst(view, ev.x, ev.y, '#9d5cff', 12);
        break;
      default:
        break;
    }
  }
}

function burst(view, x, y, color, n) {
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2;
    const sp = 1.5 + Math.random() * 3.2;
    view.particles.push({ x: x + 0.5, y: y + 0.5, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 0.6 + Math.random() * 0.4, max: 1, color });
  }
}

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.resize();
  }

  resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.w = w;
    this.h = h;
    this.canvas.width = Math.floor(w * this.dpr);
    this.canvas.height = Math.floor(h * this.dpr);
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
  }

  /** Draw one frame. dt in seconds. */
  draw(G, view, dt) {
    const ctx = this.ctx;
    view.t += dt;
    const now = view.t;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.fillStyle = '#07060c';
    ctx.fillRect(0, 0, this.w, this.h);
    if (!G.map) return;

    const m = G.map;
    const mm = modsOf(G.relics);
    const radius = mm.lantern;
    const vis = computeFov(G, G.player.x, G.player.y, radius);
    view.visible = vis;
    for (let i = 0; i < vis.length; i++) if (vis[i]) G.explored[i] = 1;

    // camera follows the player
    const targetX = G.player.x * TILE + TILE / 2 - this.w / 2;
    const targetY = G.player.y * TILE + TILE / 2 - this.h / 2;
    if (view.camX === null) {
      view.camX = targetX;
      view.camY = targetY;
    }
    view.camX += (targetX - view.camX) * Math.min(1, dt * 10);
    view.camY += (targetY - view.camY) * Math.min(1, dt * 10);
    let sx = 0;
    let sy = 0;
    if (view.shake > 0) {
      view.shake = Math.max(0, view.shake - dt);
      sx = (Math.random() - 0.5) * 10 * view.shake;
      sy = (Math.random() - 0.5) * 10 * view.shake;
    }
    const ox = Math.round(-view.camX + sx);
    const oy = Math.round(-view.camY + sy);
    this.lastOx = Math.round(-view.camX);
    this.lastOy = Math.round(-view.camY);
    view.hurt = Math.max(0, view.hurt - dt);

    const x0 = Math.max(0, Math.floor(-ox / TILE) - 1);
    const y0 = Math.max(0, Math.floor(-oy / TILE) - 1);
    const x1 = Math.min(m.w - 1, Math.ceil((this.w - ox) / TILE) + 1);
    const y1 = Math.min(m.h - 1, Math.ceil((this.h - oy) / TILE) + 1);

    // ---- terrain ----
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const px = ox + x * TILE;
        const py = oy + y * TILE;
        const t = m.tiles[y * m.w + x];
        if (t === T.WALL) {
          const below = inBounds(m, x, y + 1) && m.tiles[(y + 1) * m.w + x] !== T.WALL;
          S.drawWallTile(ctx, px, py, TILE, x, y, below);
        } else {
          S.drawFloorTile(ctx, px, py, TILE, x, y);
          if (t === T.DOOR) S.drawDoor(ctx, px, py, TILE, G.door.open);
          if (t === T.PLATE) S.drawPlate(ctx, px, py, TILE, G.turn <= G.door.openUntil, now);
          if (t === T.EXIT) S.drawExit(ctx, px, py, TILE, now);
        }
      }
    }

    // ---- items ----
    for (const it of G.items) {
      const i = it.y * m.w + it.x;
      if (!vis[i] && !G.explored[i]) continue;
      if (!vis[i]) continue;
      const cx = ox + it.x * TILE + TILE / 2;
      const cy = oy + it.y * TILE + TILE / 2;
      if (it.type === 'potion') S.drawPotion(ctx, cx, cy, TILE, now);
      else S.drawShard(ctx, cx, cy, TILE, now);
    }

    // ---- echo path preview (next steps) ----
    for (const ech of G.echoes) {
      if (ech.path.length === 0) continue;
      let cx = ech.x;
      let cy = ech.y;
      let idx = ech.cursor;
      for (let k = 0; k < 4; k++) {
        const st = ech.path[idx % ech.path.length];
        idx++;
        if (!st.wait) {
          cx += st.dx;
          cy += st.dy;
        }
        if (!inBounds(m, cx, cy) || !vis[cy * m.w + cx]) break;
        ctx.fillStyle = `rgba(102,204,255,${0.42 - k * 0.09})`;
        ctx.beginPath();
        ctx.arc(ox + cx * TILE + TILE / 2, oy + cy * TILE + TILE / 2, 3.5 - k * 0.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // ---- enemies (only visible ones) ----
    for (const e of G.enemies) {
      if (e.hp <= 0 || !vis[e.y * m.w + e.x]) continue;
      const p = this.unitPos(view, 'm' + e.id, e.x, e.y, now);
      const cx = ox + p.x * TILE + TILE / 2;
      const cy = oy + p.y * TILE + TILE / 2;
      if (e.type === 'husk') S.drawHusk(ctx, cx, cy, TILE, now + e.id);
      else if (e.type === 'sniper') S.drawSniper(ctx, cx, cy, TILE, now + e.id);
      else if (e.type === 'charger') S.drawCharger(ctx, cx, cy, TILE, now + e.id, e.wind);
      else if (e.type === 'warden') S.drawWarden(ctx, cx, cy, TILE, now);
      if (e.type === 'charger' && e.wind) {
        // telegraph: danger line in the locked direction
        ctx.strokeStyle = 'rgba(255,80,60,0.85)';
        ctx.setLineDash([6, 5]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + e.wind.dx * TILE * 4, cy + e.wind.dy * TILE * 4);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#ff5a3c';
        ctx.font = 'bold 18px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('!', cx, cy - TILE * 0.55);
      }
      if (e.state === 'chase' && e.type !== 'charger') {
        ctx.fillStyle = 'rgba(255,80,80,0.9)';
        ctx.fillRect(cx - 3, cy - TILE * 0.5, 6, 3);
      }
      this.hpBar(ctx, cx, cy - TILE * 0.5, e.hp, e.maxHp, e.type === 'warden' ? 80 : 26);
    }

    // ---- echoes ----
    for (const ech of G.echoes) {
      if (ech.hp <= 0) continue;
      const p = this.unitPos(view, 'e' + ech.id, ech.x, ech.y, now);
      const cx = ox + p.x * TILE + TILE / 2;
      const cy = oy + p.y * TILE + TILE / 2;
      if (!vis[Math.round(p.y) * m.w + Math.round(p.x)]) {
        // echoes are still drawn when visible; ghosts outside the light are hidden
        continue;
      }
      S.drawPlayer(ctx, cx, cy, TILE, { ghost: true, t: now + ech.id, lantern: false });
    }

    // ---- player ----
    {
      const p = this.unitPos(view, 'p', G.player.x, G.player.y, now);
      const cx = ox + p.x * TILE + TILE / 2;
      const cy = oy + p.y * TILE + TILE / 2;
      S.drawPlayer(ctx, cx, cy, TILE, { t: now, hurt: view.hurt });
      if (G.player.hp > 0) {
        // lantern glow
        const g = ctx.createRadialGradient(cx, cy, 4, cx, cy, TILE * 3.2);
        g.addColorStop(0, 'rgba(255,200,110,0.10)');
        g.addColorStop(1, 'rgba(255,200,110,0)');
        ctx.fillStyle = g;
        ctx.fillRect(cx - TILE * 3.2, cy - TILE * 3.2, TILE * 6.4, TILE * 6.4);
      }
    }

    // ---- darkness: unexplored black, explored-but-not-visible dimmed ----
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const i = y * m.w + x;
        if (vis[i]) continue;
        const px = ox + x * TILE;
        const py = oy + y * TILE;
        ctx.fillStyle = G.explored[i] ? 'rgba(6,5,12,0.62)' : '#000';
        ctx.fillRect(px, py, TILE, TILE);
      }
    }

    // ---- beams (shots / charges) ----
    for (let i = view.beams.length - 1; i >= 0; i--) {
      const b = view.beams[i];
      b.life -= dt;
      if (b.life <= 0) {
        view.beams.splice(i, 1);
        continue;
      }
      ctx.globalAlpha = Math.max(0, b.life / b.max);
      ctx.strokeStyle = b.color;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(ox + b.x0 * TILE + TILE / 2, oy + b.y0 * TILE + TILE / 2);
      ctx.lineTo(ox + b.x1 * TILE + TILE / 2, oy + b.y1 * TILE + TILE / 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // ---- rings ----
    for (let i = view.rings.length - 1; i >= 0; i--) {
      const r = view.rings[i];
      r.life -= dt;
      if (r.life <= 0) {
        view.rings.splice(i, 1);
        continue;
      }
      const k = 1 - r.life / r.max;
      ctx.globalAlpha = 1 - k;
      ctx.strokeStyle = r.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(ox + r.x * TILE + TILE / 2, oy + r.y * TILE + TILE / 2, TILE * (0.3 + k * 1.2), 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // ---- particles ----
    for (let i = view.particles.length - 1; i >= 0; i--) {
      const p = view.particles[i];
      p.life -= dt;
      if (p.life <= 0) {
        view.particles.splice(i, 1);
        continue;
      }
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vx *= 0.94;
      p.vy *= 0.94;
      ctx.globalAlpha = Math.max(0, Math.min(1, p.life / 0.6));
      ctx.fillStyle = p.color;
      ctx.fillRect(ox + p.x * TILE - 2, oy + p.y * TILE - 2, 4, 4);
      ctx.globalAlpha = 1;
    }

    // ---- floating texts ----
    ctx.textAlign = 'center';
    ctx.font = 'bold 16px ui-monospace, monospace';
    for (let i = view.texts.length - 1; i >= 0; i--) {
      const tx = view.texts[i];
      tx.life -= dt;
      if (tx.life <= 0) {
        view.texts.splice(i, 1);
        continue;
      }
      const k = 1 - tx.life / tx.max;
      ctx.globalAlpha = Math.max(0, tx.life / tx.max);
      ctx.fillStyle = tx.color;
      ctx.fillText(tx.text, ox + tx.x * TILE + TILE / 2, oy + tx.y * TILE - k * 18);
      ctx.globalAlpha = 1;
    }

    // ---- hurt vignette ----
    if (view.hurt > 0) {
      const g = ctx.createRadialGradient(this.w / 2, this.h / 2, this.h * 0.3, this.w / 2, this.h / 2, this.h * 0.75);
      g.addColorStop(0, 'rgba(160,0,20,0)');
      g.addColorStop(1, `rgba(160,0,20,${0.5 * (view.hurt / 0.35)})`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, this.w, this.h);
    }
  }

  unitPos(view, key, x, y, now) {
    const a = view.anims.get(key);
    if (!a) return { x, y };
    const k = Math.min(1, (now - a.t0) / MOVE_ANIM);
    if (k >= 1) {
      view.anims.delete(key);
      return { x, y };
    }
    const e = k * k * (3 - 2 * k);
    return { x: a.fx + (a.tx - a.fx) * e, y: a.fy + (a.ty - a.fy) * e };
  }

  hpBar(ctx, cx, y, hp, max, w) {
    if (hp >= max) return;
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(cx - w / 2, y, w, 4);
    ctx.fillStyle = '#ff5566';
    ctx.fillRect(cx - w / 2, y, (w * hp) / max, 4);
  }

  /** Screen -> tile conversion for mouse input (uses the last drawn camera offset). */
  tileAt(screenX, screenY) {
    if (this.lastOx === undefined) return null;
    return { x: Math.floor((screenX - this.lastOx) / TILE), y: Math.floor((screenY - this.lastOy) / TILE) };
  }
}

