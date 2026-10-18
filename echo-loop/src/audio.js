// Tiny synthesized sound effects (WebAudio). No audio files.
export class Sfx {
  constructor() {
    this.enabled = localStorage.getItem('echoloop.sound') !== 'off';
    this.ctx = null;
  }

  ensure() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      this.ctx = new AC();
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  }

  toggle() {
    this.enabled = !this.enabled;
    localStorage.setItem('echoloop.sound', this.enabled ? 'on' : 'off');
    return this.enabled;
  }

  tone(freq, dur, type = 'square', vol = 0.08, slideTo = null, delay = 0) {
    const c = this.ensure();
    if (!c || !this.enabled) return;
    const t0 = c.currentTime + delay;
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, t0);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t0 + dur);
    g.gain.setValueAtTime(vol, t0);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g).connect(c.destination);
    o.start(t0);
    o.stop(t0 + dur + 0.02);
  }

  noise(dur, vol = 0.12, delay = 0) {
    const c = this.ensure();
    if (!c || !this.enabled) return;
    const t0 = c.currentTime + delay;
    const len = Math.floor(c.sampleRate * dur);
    const buf = c.createBuffer(1, len, c.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = c.createBufferSource();
    src.buffer = buf;
    const g = c.createGain();
    g.gain.value = vol;
    src.connect(g).connect(c.destination);
    src.start(t0);
  }

  play(name) {
    switch (name) {
      case 'step':
        this.tone(180, 0.05, 'triangle', 0.035);
        break;
      case 'hit':
        this.noise(0.12, 0.18);
        this.tone(220, 0.12, 'sawtooth', 0.06, 90);
        break;
      case 'hurt':
        this.tone(200, 0.25, 'sawtooth', 0.09, 60);
        break;
      case 'kill':
        this.tone(520, 0.12, 'square', 0.05, 180);
        break;
      case 'echo_lost':
        this.tone(900, 0.3, 'sine', 0.07, 200);
        break;
      case 'plate':
        this.tone(660, 0.2, 'sine', 0.07, 990);
        break;
      case 'door':
        this.tone(120, 0.3, 'triangle', 0.06, 80);
        break;
      case 'windup':
        this.tone(260, 0.3, 'sawtooth', 0.03, 520);
        break;
      case 'charge':
        this.noise(0.25, 0.22);
        this.tone(140, 0.2, 'square', 0.05, 60);
        break;
      case 'shot':
        this.tone(1200, 0.08, 'square', 0.03, 300);
        break;
      case 'pickup':
        this.tone(740, 0.08, 'triangle', 0.07);
        this.tone(1100, 0.1, 'triangle', 0.06, null, 0.07);
        break;
      case 'rewind':
        this.tone(1400, 0.4, 'sine', 0.06, 300);
        break;
      case 'loop':
        this.tone(330, 0.5, 'sine', 0.07, 110);
        this.tone(440, 0.5, 'sine', 0.05, 165, 0.1);
        break;
      case 'exit':
        [523, 659, 784, 1046].forEach((f, i) => this.tone(f, 0.18, 'triangle', 0.07, null, i * 0.09));
        break;
      case 'relic':
        [392, 523, 659].forEach((f, i) => this.tone(f, 0.25, 'sine', 0.07, null, i * 0.07));
        break;
      case 'gameover':
        this.tone(220, 1.2, 'sawtooth', 0.06, 40);
        break;
      case 'select':
        this.tone(600, 0.05, 'square', 0.04);
        break;
      default:
        break;
    }
  }
}
