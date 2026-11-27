// Gino's feelings, shown in his body. His brain picks an emotion and his needs drift (vitals.py); this turns them into
// body language on the 3D model in world.js: he hums and wiggles his ears when he's happy, yawns and droops when he's
// tired, his tummy rumbles when he's hungry and he grumbles to himself when he's lonely or cross.
// The same code runs on /live, his private page and the video clips, so he looks the same everywhere.
import * as THREE from 'three';

const HAPPY = new Set(['happy', 'joyful', 'excited', 'content', 'proud', 'loved', 'playful', 'grateful', 'inspired', 'silly', 'hopeful', 'amazed', 'creative', 'cozy']);
const PERKY = new Set(['excited', 'playful', 'silly', 'joyful', 'amazed']);
const TIRED = new Set(['tired', 'sleepy']);
const LONELY = new Set(['lonely']);
const CROSS = new Set(['grumpy', 'angry', 'frustrated']);
const DOWN = new Set(['sad', 'lonely', 'bored', 'anxious', 'scared', 'nostalgic']);
const clamp01 = v => Math.min(1, Math.max(0, v));
const low = (v, from, to) => (typeof v === 'number' ? clamp01((from - v) / (from - to)) : 0);   // 0 at `from`, 1 at `to` and below

// How strongly he feels each thing right now, 0..1, from what he says he feels and from his needs.
export function feelings(s = {}) {
  const v = s.vitals || {}, e = String(s.emotion || '').toLowerCase().trim();
  const tired = Math.max(TIRED.has(e) ? 1 : 0, low(v.energy, 35, 10));
  const hungry = Math.max(e === 'hungry' ? 1 : 0, low(v.fullness, 35, 10));
  const lonely = Math.max(LONELY.has(e) ? 1 : 0, low(v.social, 30, 8));
  const cross = CROSS.has(e) ? 1 : 0;
  const needy = Math.max(tired, hungry, lonely, cross);
  const happy = Math.max(HAPPY.has(e) ? 1 : 0, clamp01(((v.mood ?? 50) - 62) / 16)) * (1 - 0.75 * needy);
  return { happy, perky: PERKY.has(e) ? happy : 0, tired, hungry, grumble: Math.max(lonely, cross * 0.9), down: Math.max(lonely, DOWN.has(e) ? 0.8 : 0, tired * 0.7) };
}

// A few words for the hover label, e.g. "his tummy is rumbling".
export function feelingWords(f) {
  const top = strongest(f);
  return { hum: 'humming happily', yawn: 'very sleepy', rumble: 'his tummy is rumbling', grumble: 'grumbling to himself' }[top] || '';
}
function strongest(f) {
  const c = [['rumble', f.hungry], ['yawn', f.tired], ['grumble', f.grumble], ['hum', f.happy]].sort((a, b) => b[1] - a[1])[0];
  return c[1] >= 0.35 ? c[0] : '';
}
const LEN = { hum: 3.2, yawn: 2.6, rumble: 2.2, grumble: 2.0 };
const GAP = { hum: [2, 5], yawn: [4, 8], rumble: [3.5, 7], grumble: [3.5, 7] };   // seconds between, sooner when he feels it more

// little pictures drawn on a canvas (no emoji font needed, so they also show in the server-made clips)
function sprite(draw) {
  const c = document.createElement('canvas'); c.width = c.height = 128; draw(c.getContext('2d'));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false })); s.visible = false; s.renderOrder = 3; s.userData.noAO = true; return s;
}
const note = (glyph, col) => x => {
  x.font = 'bold 92px "DejaVu Sans", "Segoe UI Symbol", "Apple Symbols", serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.lineWidth = 10; x.strokeStyle = 'rgba(255,255,255,.95)'; x.strokeText(glyph, 64, 66); x.fillStyle = col; x.fillText(glyph, 64, 66);
};
const rumbleLines = x => {
  x.lineCap = 'round';
  for (const [w, col] of [[20, 'rgba(255,255,255,.95)'], [9, '#d2602f']]) {
    x.lineWidth = w; x.strokeStyle = col;
    for (let r = 0; r < 3; r++) { x.beginPath(); for (let i = 0; i <= 40; i++) { const px = 18 + i * 2.3 + r * 4, py = 30 + r * 34 + Math.sin(i * 0.5) * 9; i ? x.lineTo(px, py) : x.moveTo(px, py); } x.stroke(); }
  }
};
const grumbleCloud = x => {
  const puff = () => { x.beginPath(); for (const [cx, cy, r] of [[40, 70, 26], [66, 54, 30], [92, 70, 24], [64, 82, 26]]) { x.moveTo(cx + r, cy); x.arc(cx, cy, r, 0, 6.3); } };
  x.fillStyle = 'rgba(255,255,255,.95)'; x.save(); x.translate(64, 68); x.scale(1.12, 1.12); x.translate(-64, -68); puff(); x.fill(); x.restore();
  x.fillStyle = '#7d8590'; puff(); x.fill();
  x.strokeStyle = '#2d2a2a'; x.lineWidth = 5; x.lineCap = 'round'; x.beginPath();   // a little scribble: mrrrm
  for (let i = 0; i <= 30; i++) { const px = 36 + i * 1.9, py = 68 + Math.sin(i * 0.95) * 10 * (i % 2 ? 1 : 0.6); i ? x.lineTo(px, py) : x.moveTo(px, py); } x.stroke();
};

export function createMoods(gino, opts = {}) {
  const G = gino.userData;
  const notes = [note('♪', '#e0567a'), note('♫', '#4a7fd6'), note('♪', '#3aa36b'), note('♫', '#d98a1c')].map(d => { const s = sprite(d); gino.add(s); return s; });
  const rumble = [sprite(rumbleLines), sprite(rumbleLines)]; rumble.forEach(s => gino.add(s));
  const cloud = sprite(grumbleCloud); gino.add(cloud);
  const M = { f: feelings(), cue: '', at: -99, next: 1.5, cueK: 0, ear: [0, 0] };
  const v = new THREE.Vector3();
  const toGino = (obj, x, y, z) => gino.worldToLocal(obj.localToWorld(v.set(x, y, z)));
  // where his mouth is, in Gino's own frame: on the sculpted model (G.real) the face is found with G.faceAt
  const mouthAt = (fwd = 0, up = 0) => {
    if (G.faceAt) { gino.worldToLocal(G.faceAt(v)); v.x += 0.22 + fwd; v.y += -0.12 + up; return v; }
    return toGino(G.head, 0.8 + fwd, up, 0);
  };
  // the sculpted model hides the simple shapes, so move the yawn mouth onto its head bone, at the front of its snout
  let mouthK = 1;
  function fitMouth() {
    const hb = G.real.getObjectByName('head'); if (!hb) return;
    G.mouth.traverse(o => { if (o.isMesh) o.visible = true; });
    G.body.add(G.mouth); G.mouth.position.set(1.45, 0.95, 0); G.mouth.rotation.set(0, 0, 0); G.mouth.scale.setScalar(1);
    hb.attach(G.mouth); mouthK = G.mouth.scale.x * 1.25;   // keep its size in the bone's units, a bit wider for the bigger snout
  }

  return {
    get feeling() { return M.f; },
    get cue() { return M.cue; },
    update(state) { M.f = feelings(state); },
    // How much slower he walks when he's tired or low.
    get pace() { return 1 - 0.3 * M.f.tired - 0.12 * M.f.down * (1 - M.f.tired); },
    // Runs every frame after world.js has posed him for what he's doing; adds his feelings on top.
    // still: 1 when he's standing about, 0 while he's busy (rolling, napping, swimming...) so moods don't fight the action.
    apply(t, dt, { awake, still }) {
      const f = M.f, k = awake ? 1 : 0;
      if (G.real && !M.fitted) { M.fitted = true; fitMouth(); }
      M.cueK = THREE.MathUtils.lerp(M.cueK, k, Math.min(1, dt * 4));
      if (!awake) { M.cue = ''; M.next = Math.max(M.next, t + 2); }
      else if (t > M.next) {
        const c = strongest(f);
        if (c) { M.cue = c; M.at = t; opts.onCue?.(c); }
        const [a, b] = GAP[c || 'hum'], w = c ? f[{ hum: 'happy', yawn: 'tired', rumble: 'hungry', grumble: 'grumble' }[c]] : 0;
        M.next = t + (LEN[c] || 0) + (a + Math.random() * (b - a)) * (1.25 - 0.5 * w);
      }
      const e = t - M.at, cue = M.cue && e < LEN[M.cue] ? M.cue : '', ph = cue ? e / LEN[cue] : 0, bell = Math.sin(Math.PI * clamp01(ph)) * M.cueK;
      if (!cue) M.cue = '';

      // posture: droopy head and ears when tired or low, a happy little sway when content
      const droop = f.down * k, sway = f.happy * k * still;
      G.head.rotation.z += -0.26 * droop + 0.05 * sway;
      G.body.rotation.z += -0.05 * droop;   // shoulders sag a little
      G.body.rotation.x += Math.sin(t * 2.1) * 0.035 * sway;
      G.body.position.y += Math.abs(Math.sin(t * 4.2)) * 0.035 * f.perky * k * still;
      G.ears.forEach((ear, i) => {
        const s = i ? 1 : -1;
        let out = 0.8 * droop, back = 0.6 * droop;
        if (f.happy > 0.3 && k) {   // happy ear wiggles: little bursts of quick flicks, one ear then the other
          const burst = Math.max(0, Math.sin(t * 1.3 + i * 0.6)) ** 6, flick = Math.sin(t * 22 + i * 1.7) * burst;
          out += 0.22 * f.happy * flick; back += 0.18 * f.happy * Math.max(0, flick);
        }
        if (cue === 'grumble') back += 0.45 * bell;
        ear.rotation.x = ear.rotation.x * (1 - droop) + s * out;
        ear.rotation.z = back;
      });
      const eyeOpen = 1 - 0.45 * f.tired * k;
      G.eyes.forEach(eye => { eye.scale.y *= eyeOpen; });

      // yawn: nose up, mouth wide open, eyes squeezed shut, then a little shake
      const yawn = cue === 'yawn' ? Math.sin(Math.PI * clamp01(ph * 1.15)) * M.cueK : 0;
      G.head.rotation.z += 0.42 * yawn;
      G.body.position.y += 0.03 * yawn;
      if (yawn > 0.35) G.eyes.forEach(eye => { eye.scale.y = 0.018; });
      G.mouth.scale.set((1 + 0.3 * yawn) * mouthK, (0.0001 + 0.16 * yawn) * mouthK, (1 + 0.35 * yawn) * mouthK); G.mouth.visible = yawn > 0.02;
      G.legs.forEach((l, i) => { if (i < 2) l.rotation.z += 0.12 * yawn; });   // front legs stretch forward a touch

      // tummy rumble: his body wobbles, rumble lines by his belly and he looks down at it
      const rum = cue === 'rumble' ? bell : 0;
      G.body.position.z += Math.sin(t * 46) * 0.018 * rum;
      G.body.scale.x *= 1 + Math.sin(t * 31) * 0.015 * rum;
      G.head.rotation.z -= 0.38 * rum; G.head.rotation.y += 0.28 * rum;
      rumble.forEach((s, i) => {
        const side = i ? 1 : -1, wob = Math.sin(t * 20 + i) * 0.03;
        s.visible = rum > 0.05; if (!s.visible) return;
        toGino(G.body, (G.real ? 0 : 0.3) + wob, 0.45, side * (G.real ? 0.78 : 0.66)); s.position.copy(v); s.scale.setScalar(0.42 * rum + 0.1); s.material.opacity = Math.min(1, rum * 1.6);
      });

      // grumble: a little grey cloud by his head and a grumpy shake of the head
      const gr = cue === 'grumble' ? bell : 0;
      G.head.rotation.y += Math.sin(t * 9) * 0.16 * gr; G.head.rotation.z -= 0.1 * gr;
      cloud.visible = gr > 0.05;
      if (cloud.visible) { mouthAt(-0.2, 0.75 + ph * 0.25); cloud.position.copy(v); cloud.scale.setScalar(0.25 + 0.3 * gr); cloud.material.opacity = Math.min(1, gr * 1.7); }

      // humming: musical notes float up from his mouth, his head bobs to the tune
      const hum = cue === 'hum' ? M.cueK : 0;
      G.head.rotation.z += Math.sin(t * 5.5) * 0.06 * hum * Math.min(1, e * 2) * (1 - clamp01((e - LEN.hum + 0.5) * 2));
      mouthAt(); const mx = v.x, my = v.y, mz = v.z;
      notes.forEach((n, i) => {
        const nk = (e - i * 0.55) / 1.7;
        n.visible = hum > 0 && nk > 0 && nk < 1 && e - i * 0.55 < LEN.hum - 0.6; if (!n.visible) return;
        n.position.set(mx + 0.1 + nk * 0.2, my + 0.25 + nk * 1.2, mz + Math.sin(nk * 6 + i) * 0.2);
        n.scale.setScalar(0.22 + Math.sin(nk * Math.PI) * 0.12); n.material.opacity = 1 - nk * nk;
      });
    },
  };
}
