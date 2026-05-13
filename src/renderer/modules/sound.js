import { get } from './storage.js';

let ctx = null;
function ensureCtx() {
  if (ctx) return ctx;
  const C = window.AudioContext || window.webkitAudioContext;
  if (!C) return null;
  ctx = new C();
  return ctx;
}

function chime() {
  if (!get().settings.soundOn) return;
  const ac = ensureCtx();
  if (!ac) return;
  const now = ac.currentTime;
  const tones = [880, 1318];
  tones.forEach((freq, i) => {
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.value = 0;
    osc.connect(gain).connect(ac.destination);
    const start = now + i * 0.18;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(0.12, start + 0.04);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 1.4);
    osc.start(start);
    osc.stop(start + 1.5);
  });
}

export { chime };
