// Generates the demo logo used by the sample project. Output is committed (≈ few KB).
import { createCanvas } from '@napi-rs/canvas';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const c = createCanvas(320, 180);
const g = c.getContext('2d');
const grad = g.createLinearGradient(0, 0, 320, 180);
grad.addColorStop(0, '#ff7a59');
grad.addColorStop(1, '#4f8cff');
g.fillStyle = grad;
g.fillRect(0, 0, 320, 180);
g.fillStyle = '#ffffff';
g.beginPath();
g.arc(160, 90, 60, 0, Math.PI * 2);
g.fill();
g.fillStyle = '#16181d';
g.font = 'bold 40px sans-serif';
g.textAlign = 'center';
g.textBaseline = 'middle';
g.fillText('LIVE', 160, 92);
const out = fileURLToPath(new URL('../assets/logo.png', import.meta.url));
writeFileSync(out, c.toBuffer('image/png'));
console.log(`written ${out}`);
