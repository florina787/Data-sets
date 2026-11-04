/** Tiny synthesised UI sounds (Web Audio). Muted by default; nothing plays unless the user unmutes. */
let ctx: AudioContext | null = null;
function ac(): AudioContext | null {
  try { ctx ??= new (window.AudioContext || (window as any).webkitAudioContext)(); return ctx; } catch { return null; }
}
function tone(freq: number, ms: number, type: OscillatorType = "sine", gain = 0.05, delay = 0) {
  const a = ac();
  if (!a) return;
  const o = a.createOscillator(), g = a.createGain();
  o.type = type; o.frequency.value = freq;
  const t = a.currentTime + delay;
  g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(gain, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + ms / 1000);
  o.connect(g).connect(a.destination); o.start(t); o.stop(t + ms / 1000 + 0.02);
}
export const sound = {
  step: () => tone(140 + Math.random() * 30, 70, "triangle", 0.03),
  chime: () => { tone(784, 220); tone(1046, 320, "sine", 0.05, 0.12); },
  alert: () => { tone(330, 180, "square", 0.03); tone(262, 260, "square", 0.03, 0.16); },
};
