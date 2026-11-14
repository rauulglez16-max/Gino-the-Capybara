// Gino's 3D world. three.js r186, WebGLRenderer, everything procedural (no model files).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const CELL = 2, GW = 16, GH = 10;
const cellX = x => (x - (GW - 1) / 2) * CELL;
const cellZ = y => (y - (GH - 1) / 2) * CELL;

// ---------------------------------------------------------------- terrain shape
function hills(x, z) {
  return Math.sin(x * 0.21) * Math.cos(z * 0.17) * 0.9 + Math.sin(x * 0.07 + 1.3) * Math.sin(z * 0.09 + 0.4) * 2.2;
}
export function groundY(x, z) {
  // Flat-ish meadow where Gino lives, rolling hills around it.
  const dx = Math.max(0, Math.abs(x) - GW), dz = Math.max(0, Math.abs(z) - GH);
  const out = Math.min(1, Math.hypot(dx, dz) / 14);
  const e = out * out * (3 - 2 * out);
  return hills(x, z) * (0.12 + e * 1.6) + e * 2.5;
}

// ---------------------------------------------------------------- tiny modelling kit
const mats = new Map();
function mat(color, extra = {}) {
  const key = color + JSON.stringify(extra);
  if (!mats.has(key)) mats.set(key, new THREE.MeshStandardMaterial({ color, roughness: 0.9, flatShading: true, ...extra }));
  return mats.get(key);
}
const geos = {
  box: new THREE.BoxGeometry(1, 1, 1),
  sphere: new THREE.IcosahedronGeometry(0.5, 1),
  smooth: new THREE.SphereGeometry(0.5, 20, 14),
  cyl: new THREE.CylinderGeometry(0.5, 0.5, 1, 10),
  cone: new THREE.ConeGeometry(0.5, 1, 8),
  disc: new THREE.CylinderGeometry(0.5, 0.5, 1, 28),
  torus: new THREE.TorusGeometry(0.5, 0.18, 8, 18),
};
function part(parent, geo, color, [sx, sy, sz], [px, py, pz], rot, extra) {
  const m = new THREE.Mesh(geos[geo], typeof color === 'object' && color.isMaterial ? color : mat(color, extra));
  m.scale.set(sx, sy, sz); m.position.set(px, py, pz);
  if (rot) m.rotation.set(rot[0], rot[1], rot[2]);
  m.castShadow = true; m.receiveShadow = true;
  parent.add(m); return m;
}
// Deterministic randomness per item so the world doesn't reshuffle on refresh.
function rng(seed) { let s = (seed * 9301 + 49297) % 233280; return () => (s = (s * 9301 + 49297) % 233280) / 233280; }

// ---------------------------------------------------------------- things Gino can build
const B = {
  tree(g, o, r) {
    part(g, 'cyl', '#7a5230', [0.35, 1.6, 0.35], [0, 0.8, 0]);
    const c = o.color || '#5d9c4a';
    part(g, 'sphere', c, [2.0, 1.7, 2.0], [0, 2.2, 0]);
    part(g, 'sphere', c, [1.3, 1.2, 1.3], [0.6, 2.9, 0.2]);
    part(g, 'sphere', c, [1.2, 1.0, 1.2], [-0.6, 2.7, -0.3]);
  },
  fruit_tree(g, o, r) {
    B.tree(g, { color: '#4f9446' }, r);
    const fc = o.color || (/apple|cherry/.test(o.name) ? '#d9463e' : /lemon|banana/.test(o.name) ? '#f2d64b' : '#f39a2e');
    for (let i = 0; i < 9; i++) { const a = r() * 6.28, h = 1.8 + r() * 1.3; part(g, 'sphere', fc, [0.22, 0.22, 0.22], [Math.cos(a) * 0.95, h, Math.sin(a) * 0.95]); }
  },
  pine(g, o) {
    part(g, 'cyl', '#6e4a2c', [0.3, 1, 0.3], [0, 0.5, 0]);
    const c = o.color || '#3f7d4e';
    part(g, 'cone', c, [2, 1.6, 2], [0, 1.5, 0]); part(g, 'cone', c, [1.5, 1.4, 1.5], [0, 2.4, 0]); part(g, 'cone', c, [1, 1.2, 1], [0, 3.2, 0]);
  },
  pond(g, o, r) {
    const w = part(g, 'disc', o.color || '#5fb4dc', [3.4, 0.06, 2.8], [0, 0.04, 0], null, { transparent: true, opacity: 0.82, roughness: 0.15, metalness: 0.1, flatShading: false });
    w.castShadow = false; w.userData.water = true;
    part(g, 'disc', '#3d8fb8', [2.6, 0.05, 2.1], [0, 0.03, 0]).castShadow = false;
    for (let i = 0; i < 11; i++) { const a = i / 11 * 6.28 + r() * 0.3, s = 0.25 + r() * 0.3; part(g, 'sphere', '#9a968c', [s, s * 0.6, s], [Math.cos(a) * 1.75, 0.08, Math.sin(a) * 1.45]); }
    for (let i = 0; i < 3; i++) { const a = r() * 6.28, d = r() * 0.9; part(g, 'disc', '#6bbf59', [0.42, 0.03, 0.42], [Math.cos(a) * d, 0.09, Math.sin(a) * d]).castShadow = false; }
    for (let i = 0; i < 4; i++) { const a = r() * 6.28; part(g, 'cyl', '#7fae52', [0.05, 0.9, 0.05], [Math.cos(a) * 1.6, 0.45, Math.sin(a) * 1.3], [0, 0, (r() - 0.5) * 0.3]); }
  },
  garden(g, o, r) {
    part(g, 'box', '#6b4a2f', [1.8, 0.18, 1.8], [0, 0.09, 0]);
    const veg = ['#f08a2c', '#e0503d', '#f2c14e', '#8fce5b', '#b565c9'];
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      part(g, 'cone', '#58a84a', [0.3, 0.42, 0.3], [i * 0.55, 0.38, j * 0.55]);
      part(g, 'sphere', veg[Math.floor(r() * veg.length)], [0.2, 0.2, 0.2], [i * 0.55 + 0.12, 0.24, j * 0.55 + 0.08]);
    }
    for (const [x, z] of [[-0.9, -0.9], [0.9, -0.9], [-0.9, 0.9], [0.9, 0.9]]) part(g, 'cyl', '#8a6642', [0.08, 0.5, 0.08], [x, 0.25, z]);
  },
  bed(g, o) {
    part(g, 'torus', o.color || '#e3c878', [1.7, 1.7, 1.3], [0, 0.18, 0], [Math.PI / 2, 0, 0]);
    part(g, 'disc', '#f1dc9c', [1.5, 0.16, 1.5], [0, 0.1, 0]);
    part(g, 'sphere', '#f7efe2', [0.6, 0.25, 0.4], [-0.35, 0.28, 0]);
  },
  hammock(g, o) {
    part(g, 'cyl', '#7a5230', [0.14, 1.7, 0.14], [-1.2, 0.85, 0]); part(g, 'cyl', '#7a5230', [0.14, 1.7, 0.14], [1.2, 0.85, 0]);
    const c = o.color || '#e0705a';
    for (let i = -4; i <= 4; i++) { const x = i * 0.26, y = 0.75 + (i * i) * 0.045; part(g, 'box', i % 2 ? c : '#f6e9d2', [0.27, 0.05, 0.8], [x, y, 0], [0, 0, -i * 0.09]); }
  },
  bookshelf(g, o, r) {
    part(g, 'box', o.color || '#9a6b3f', [1.5, 1.8, 0.45], [0, 0.9, 0]);
    const cols = ['#d9534f', '#4f8bd9', '#58b368', '#e8b84a', '#9a6fd1', '#e88a4a'];
    for (let row = 0; row < 3; row++) {
      part(g, 'box', '#3d2a18', [1.34, 0.46, 0.1], [0, 0.35 + row * 0.56, 0.2]);
      for (let i = 0; i < 7; i++) part(g, 'box', cols[Math.floor(r() * 6)], [0.14, 0.3 + r() * 0.12, 0.2], [-0.54 + i * 0.18, 0.3 + row * 0.56, 0.24]);
    }
  },
  flowers(g, o, r) {
    const sun = /sunflower/.test(o.name);
    const cols = o.color ? [o.color] : sun ? ['#f6c833'] : ['#f27ca0', '#f6c833', '#ffffff', '#b78cf0', '#f2603d'];
    for (let i = 0; i < (sun ? 6 : 11); i++) {
      const x = (r() - 0.5) * 1.6, z = (r() - 0.5) * 1.6, h = sun ? 1.1 + r() * 0.6 : 0.3 + r() * 0.3;
      part(g, 'cyl', '#4d9a45', [0.05, h, 0.05], [x, h / 2, z]);
      part(g, 'sphere', cols[Math.floor(r() * cols.length)], sun ? [0.42, 0.42, 0.12] : [0.2, 0.2, 0.2], [x, h, z]);
      if (sun) part(g, 'sphere', '#6b4423', [0.2, 0.2, 0.16], [x, h, z]);
    }
  },
  rock(g, o, r) {
    const c = o.color || '#9b978f';
    part(g, 'sphere', c, [1.3, 0.9, 1.1], [0, 0.35, 0], [r(), r(), r()]);
    part(g, 'sphere', c, [0.7, 0.5, 0.6], [0.7, 0.2, 0.3], [r(), r(), r()]);
  },
  lamp(g, o) {
    part(g, 'cyl', '#4a4a52', [0.1, 1.7, 0.1], [0, 0.85, 0]);
    part(g, 'box', '#4a4a52', [0.42, 0.08, 0.42], [0, 1.95, 0]);
    const bulb = part(g, 'sphere', '#ffe9a8', [0.34, 0.34, 0.34], [0, 1.75, 0], null, { emissive: o.color || '#ffcf66', emissiveIntensity: 1.2 });
    bulb.castShadow = false;
    const l = new THREE.PointLight(o.color || '#ffcf66', 0, 9, 1.6); l.position.set(0, 1.75, 0); l.userData.nightLight = 14; g.add(l);
  },
  house(g, o) {
    part(g, 'box', o.color || '#e8d3b0', [1.9, 1.3, 1.7], [0, 0.65, 0]);
    part(g, 'cone', '#b5553c', [2.9, 1.1, 2.9], [0, 1.85, 0], [0, Math.PI / 4, 0]).geometry = new THREE.ConeGeometry(0.5, 1, 4);
    part(g, 'box', '#6b4a2f', [0.5, 0.8, 0.06], [0, 0.4, 0.86]);
    part(g, 'box', '#a9d8ee', [0.36, 0.36, 0.06], [0.6, 0.8, 0.86]);
  },
  fence(g, o) {
    for (let i = -2; i <= 2; i++) part(g, 'box', o.color || '#b98d5a', [0.12, 0.8, 0.12], [i * 0.45, 0.4, 0]);
    part(g, 'box', o.color || '#b98d5a', [1.95, 0.1, 0.07], [0, 0.6, 0]); part(g, 'box', o.color || '#b98d5a', [1.95, 0.1, 0.07], [0, 0.3, 0]);
  },
  bench(g, o) {
    part(g, 'box', o.color || '#a87645', [1.6, 0.1, 0.5], [0, 0.5, 0]); part(g, 'box', o.color || '#a87645', [1.6, 0.5, 0.08], [0, 0.85, -0.22]);
    for (const x of [-0.65, 0.65]) part(g, 'box', '#5a5a60', [0.1, 0.5, 0.45], [x, 0.25, 0]);
  },
  table(g, o) {
    part(g, 'disc', o.color || '#b98d5a', [1.4, 0.1, 1.4], [0, 0.7, 0]); part(g, 'cyl', '#8a6642', [0.2, 0.7, 0.2], [0, 0.35, 0]);
  },
  campfire(g, o) {
    for (let i = 0; i < 7; i++) { const a = i / 7 * 6.28; part(g, 'sphere', '#8d8a84', [0.3, 0.22, 0.3], [Math.cos(a) * 0.6, 0.08, Math.sin(a) * 0.6]); }
    part(g, 'cyl', '#6b4423', [0.12, 0.9, 0.12], [0, 0.15, 0], [0, 0, 1.3]); part(g, 'cyl', '#6b4423', [0.12, 0.9, 0.12], [0, 0.15, 0], [1.3, 0, 0]);
    const f = part(g, 'cone', '#ff9a3c', [0.5, 0.9, 0.5], [0, 0.55, 0], null, { emissive: '#ff6a00', emissiveIntensity: 1.6 });
    f.castShadow = false; f.userData.flame = true;
    const l = new THREE.PointLight('#ff8a3c', 4, 8, 1.6); l.position.set(0, 0.8, 0); l.userData.nightLight = 16; l.userData.flicker = true; g.add(l);
  },
  mushroom(g, o) {
    for (const [x, z, s] of [[0, 0, 1], [0.5, 0.3, 0.6], [-0.4, 0.4, 0.45]]) {
      part(g, 'cyl', '#f4ead8', [0.22 * s, 0.6 * s, 0.22 * s], [x, 0.3 * s, z]);
      part(g, 'sphere', o.color || '#d9463e', [0.9 * s, 0.5 * s, 0.9 * s], [x, 0.65 * s, z]);
    }
  },
  statue(g, o) {
    part(g, 'box', '#b9b4aa', [0.9, 0.3, 0.9], [0, 0.15, 0]);
    part(g, 'sphere', o.color || '#cfc9bd', [0.7, 0.9, 0.7], [0, 0.85, 0]); part(g, 'sphere', o.color || '#cfc9bd', [0.45, 0.45, 0.45], [0, 1.5, 0]);
  },
  easel(g, o) {
    for (const [x, rz] of [[-0.35, 0.2], [0.35, -0.2]]) part(g, 'box', '#8a6642', [0.07, 1.6, 0.07], [x, 0.8, 0], [0.15, 0, rz]);
    part(g, 'box', '#8a6642', [0.07, 1.5, 0.07], [0, 0.75, -0.35], [-0.3, 0, 0]);
    part(g, 'box', '#fbf7ee', [0.95, 0.75, 0.05], [0, 1.05, 0.08], [0.15, 0, 0]);
    part(g, 'sphere', o.color || '#f2603d', [0.3, 0.3, 0.03], [-0.1, 1.1, 0.13], [0.15, 0, 0]); part(g, 'sphere', '#4f8bd9', [0.22, 0.22, 0.03], [0.2, 0.95, 0.13], [0.15, 0, 0]);
  },
  bush(g, o) {
    const c = o.color || '#62a653';
    part(g, 'sphere', c, [1.1, 0.8, 1.0], [0, 0.35, 0]); part(g, 'sphere', c, [0.8, 0.6, 0.8], [0.55, 0.3, 0.2]); part(g, 'sphere', c, [0.7, 0.6, 0.7], [-0.5, 0.28, -0.2]);
  },
  sign(g, o) {
    part(g, 'box', '#8a6642', [0.1, 1.1, 0.1], [0, 0.55, 0]); part(g, 'box', o.color || '#e8d3a8', [0.95, 0.5, 0.08], [0, 1.05, 0.04]);
  },
};
const KEYWORDS = [
  [/pond|pool|lake|water|spring|bath|puddle|river/, 'pond'], [/garden|vegetable|veggie|crop|farm|patch of (carrot|corn)/, 'garden'],
  [/hammock/, 'hammock'], [/fire\b|bonfire/, 'campfire'], [/\bbed|nest|pillow|cushion|blanket/, 'bed'], [/book|library|shelf/, 'bookshelf'],
  [/orange|apple|lemon|fruit|cherry|peach|mango|banana/, 'fruit_tree'], [/\b(pine|fir|spruce)/, 'pine'], [/tree|willow|oak|shade/, 'tree'],
  [/flower|sunflower|tulip|daisy|rose|lily|blossom|meadow/, 'flowers'], [/rock|stone|boulder|pebble/, 'rock'],
  [/lamp|lantern|\blight|candle/, 'lamp'], [/house|hut|den|cabin|home|shed|burrow|studio/, 'house'], [/fence|gate/, 'fence'],
  [/bench|seat|chair|sofa/, 'bench'], [/table|desk/, 'table'], [/mushroom|toadstool/, 'mushroom'],
  [/statue|sculpture|monument|totem/, 'statue'], [/easel|paint|\bart\b|canvas|gallery/, 'easel'], [/bush|shrub|hedge|fern/, 'bush'], [/\bsign|signpost|noticeboard/, 'sign'],
];
function pickKind(it) {
  if (it.kind && B[it.kind]) return it.kind;
  const n = (it.name || '').toLowerCase();
  for (const [re, k] of KEYWORDS) if (re.test(n)) return k;
  return null;
}
function emojiSprite(emoji) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'); x.font = '96px serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(emoji || '📦', 64, 70);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true }));
}
function buildItem(it) {
  const g = new THREE.Group();
  const kind = pickKind(it), r = rng(it.id * 7 + 3);
  const o = { name: (it.name || '').toLowerCase(), color: /^#[0-9a-f]{6}$/i.test(it.color || '') ? it.color : null };
  if (kind) B[kind](g, o, r);
  else { // unknown thing: a little plinth with its emoji floating above
    part(g, 'disc', '#d9cdb8', [0.9, 0.12, 0.9], [0, 0.06, 0]);
    const s = emojiSprite(it.emoji); s.scale.set(1.5, 1.5, 1); s.position.y = 1.0; s.userData.bob = true; g.add(s);
  }
  if (kind !== 'pond') g.rotation.y = Math.floor(r() * 8) * Math.PI / 4 * (kind === 'bookshelf' || kind === 'house' || kind === 'easel' || kind === 'sign' || kind === 'bench' ? 0 : 1);
  g.scale.setScalar(Math.min(2.5, Math.max(0.4, it.size || 1)));
  g.traverse(n => { n.userData.item = it; });
  g.userData.kind = kind;
  return g;
}

// ---------------------------------------------------------------- Gino himself
function buildGino() {
  const g = new THREE.Group(), fur = '#a8743f', dark = '#7d5530';
  const sm = { flatShading: false };
  const body = new THREE.Group(); g.add(body);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.48, 0.75, 6, 14), mat(fur, sm));
  torso.rotation.z = Math.PI / 2; torso.position.y = 0.72; torso.scale.set(1, 1, 1.08); torso.castShadow = true; body.add(torso);
  const head = new THREE.Group(); head.position.set(0.72, 0.98, 0); body.add(head);
  part(head, 'smooth', fur, [0.72, 0.62, 0.62], [0.05, 0, 0], null, sm);
  part(head, 'smooth', '#b58450', [0.5, 0.42, 0.5], [0.38, -0.08, 0], null, sm);
  part(head, 'smooth', dark, [0.2, 0.14, 0.26], [0.6, -0.02, 0], null, sm);
  const ears = [], eyes = [];
  for (const s of [-1, 1]) {
    ears.push(part(head, 'smooth', dark, [0.16, 0.16, 0.1], [-0.12, 0.3, s * 0.2], null, sm));
    const e = part(head, 'smooth', '#1f1711', [0.1, 0.1, 0.06], [0.22, 0.1, s * 0.27], null, { ...sm, roughness: 0.2 }); eyes.push(e);
  }
  const legs = [];
  for (const [x, z] of [[0.42, 0.26], [0.42, -0.26], [-0.42, 0.26], [-0.42, -0.26]]) {
    const pivot = new THREE.Group(); pivot.position.set(x, 0.45, z); body.add(pivot);
    part(pivot, 'cyl', dark, [0.19, 0.45, 0.19], [0, -0.22, 0], null, sm); legs.push(pivot);
  }
  const zs = [];
  for (let i = 0; i < 3; i++) {
    const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d');
    x.font = 'bold 48px sans-serif'; x.fillStyle = '#cfd8ff'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('z', 32, 32);
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false }));
    s.visible = false; g.add(s); zs.push(s);
  }
  g.userData = { body, head, legs, ears, eyes, zs };
  return g;
}

// ---------------------------------------------------------------- the world
export function createWorld(container, tooltip) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.NeutralToneMapping;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog('#bfe3f5', 55, 150);
  const camera = new THREE.PerspectiveCamera(42, 16 / 10, 0.1, 400);
  camera.position.set(-11, 11, 19);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.5, 0); controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI / 2 - 0.08; controls.minDistance = 5; controls.maxDistance = 60;
  controls.autoRotate = true; controls.autoRotateSpeed = 0.35;
  let idleAt = 0;
  controls.addEventListener('start', () => { controls.autoRotate = false; idleAt = Infinity; });
  controls.addEventListener('end', () => { idleAt = performance.now() + 20000; });

  const hemi = new THREE.HemisphereLight('#dff3ff', '#7fae62', 1.0); scene.add(hemi);
  const sun = new THREE.DirectionalLight('#fff3d6', 2.4);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -26, right: 26, top: 22, bottom: -22, near: 1, far: 120 });
  sun.shadow.bias = -0.0005; sun.shadow.normalBias = 0.04;
  scene.add(sun, sun.target);
  const sunBall = new THREE.Mesh(geos.smooth, new THREE.MeshBasicMaterial({ color: '#fff2b0', fog: false })); sunBall.scale.setScalar(9); scene.add(sunBall);
  const moon = new THREE.Mesh(geos.smooth, new THREE.MeshBasicMaterial({ color: '#e8ecff', fog: false })); moon.scale.setScalar(6); scene.add(moon);

  // ground
  const tg = new THREE.PlaneGeometry(220, 220, 110, 110); tg.rotateX(-Math.PI / 2);
  const pos = tg.attributes.position, cols = new Float32Array(pos.count * 3), c = new THREE.Color();
  const rr = rng(11);
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i), y = groundY(x, z);
    pos.setY(i, y);
    c.setHSL(0.28 - Math.min(0.06, y * 0.008), 0.55, 0.40 + (rr() - 0.5) * 0.06 - Math.min(0.1, y * 0.01));
    cols.set([c.r, c.g, c.b], i * 3);
  }
  tg.setAttribute('color', new THREE.BufferAttribute(cols, 3)); tg.computeVertexNormals();
  const ground = new THREE.Mesh(tg, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, flatShading: true }));
  ground.receiveShadow = true; scene.add(ground);

  // grass tufts and wild scenery around the meadow
  const r2 = rng(5), dummy = new THREE.Object3D();
  const tuft = new THREE.InstancedMesh(new THREE.ConeGeometry(0.07, 0.4, 4), mat('#4f9a3f'), 900); tuft.receiveShadow = true;
  for (let i = 0; i < 900; i++) {
    const x = (r2() - 0.5) * 60, z = (r2() - 0.5) * 44;
    dummy.position.set(x, groundY(x, z) + 0.18, z); dummy.rotation.set((r2() - 0.5) * 0.4, r2() * 6, (r2() - 0.5) * 0.4); dummy.scale.setScalar(0.6 + r2()); dummy.updateMatrix(); tuft.setMatrixAt(i, dummy.matrix);
  }
  scene.add(tuft);
  for (let i = 0; i < 70; i++) {
    const a = r2() * 6.28, d = 26 + r2() * 45, x = Math.cos(a) * d * 1.25, z = Math.sin(a) * d;
    const g = new THREE.Group(); (r2() < 0.45 ? B.pine : r2() < 0.8 ? B.tree : B.rock)(g, { name: '' }, r2);
    g.position.set(x, groundY(x, z) - 0.05, z); g.scale.setScalar(0.9 + r2() * 1.3); scene.add(g);
  }
  // clouds
  const clouds = [];
  for (let i = 0; i < 9; i++) {
    const g = new THREE.Group(), m = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 1, flatShading: true, transparent: true, opacity: 0.92 });
    for (let j = 0; j < 4; j++) { const p = part(g, 'sphere', m, [4 + r2() * 4, 2 + r2() * 1.5, 3 + r2() * 2], [j * 2.6 - 4, r2(), r2() * 2]); p.castShadow = false; p.receiveShadow = false; }
    g.position.set((r2() - 0.5) * 160, 24 + r2() * 10, (r2() - 0.5) * 140); scene.add(g); clouds.push(g);
  }
  // stars
  const sp = new Float32Array(900 * 3);
  for (let i = 0; i < 900; i++) { const v = new THREE.Vector3().setFromSphericalCoords(180, Math.acos(r2() * 0.95), r2() * 6.28); sp.set([v.x, v.y, v.z], i * 3); }
  const sgeo = new THREE.BufferGeometry(); sgeo.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  const stars = new THREE.Points(sgeo, new THREE.PointsMaterial({ color: '#ffffff', size: 1.1, sizeAttenuation: false, transparent: true, opacity: 0, fog: false })); scene.add(stars);
  // fireflies (night) / butterflies (day)
  const flies = [];
  for (let i = 0; i < 14; i++) {
    const m = new THREE.Mesh(geos.sphere, new THREE.MeshBasicMaterial({ color: '#f6ff9a', transparent: true })); m.scale.setScalar(0.09);
    m.userData = { a: r2() * 6.28, r: 3 + r2() * 12, h: 0.6 + r2() * 1.6, s: 0.1 + r2() * 0.25, c: new THREE.Color().setHSL(r2(), 0.8, 0.65) }; scene.add(m); flies.push(m);
  }

  const gino = buildGino(); scene.add(gino);
  const G = gino.userData;
  const itemsGroup = new THREE.Group(); scene.add(itemsGroup);
  const itemObjs = new Map(); let ponds = [];
  let state = { pos: [7, 5], asleep: false, activity: '' }, target = new THREE.Vector3(0, 0, 0), placed = false;
  let follow = false, timeMode = 'auto';

  function dispose(o) { o.traverse(n => { if (n.isSprite) { n.material.map?.dispose(); n.material.dispose(); } }); }

  function update(s) {
    state = s;
    const seen = new Set();
    for (const it of s.habitat) {
      seen.add(it.id);
      const sig = [it.name, it.emoji, it.kind, it.color, it.size].join('|');
      let o = itemObjs.get(it.id);
      if (o && o.userData.sig !== sig) { itemsGroup.remove(o); dispose(o); o = null; }
      if (!o) { o = buildItem(it); o.userData.sig = sig; itemsGroup.add(o); itemObjs.set(it.id, o); o.scale.multiplyScalar(0.01); o.userData.grow = Math.min(2.5, Math.max(0.4, it.size || 1)); }
      const x = cellX(it.x), z = cellZ(it.y); o.position.set(x, groundY(x, z), z);
    }
    for (const [id, o] of itemObjs) if (!seen.has(id)) { itemsGroup.remove(o); dispose(o); itemObjs.delete(id); }
    ponds = [...itemObjs.values()].filter(o => o.userData.kind === 'pond');
    target.set(cellX(s.pos[0]) + 0.9, 0, cellZ(s.pos[1]) + 0.9);
    const p = ponds.find(o => Math.hypot(o.position.x - cellX(s.pos[0]), o.position.z - cellZ(s.pos[1])) < 0.1);
    if (p) target.set(p.position.x, 0, p.position.z); // he's in the water
    if (!placed) { gino.position.copy(target); placed = true; }
  }

  function sky(hour) {
    const el = Math.sin((hour - 6) / 12 * Math.PI);           // -1 midnight .. 1 noon
    const day = THREE.MathUtils.smoothstep(el, -0.12, 0.28);
    const glow = Math.max(0, 1 - Math.abs(el) / 0.32) * (el > -0.2 ? 1 : 0);
    const top = new THREE.Color('#0b1430').lerp(new THREE.Color('#8fd0f2'), day).lerp(new THREE.Color('#f6a56b'), glow * 0.55);
    scene.background = top; scene.fog.color.copy(top).lerp(new THREE.Color('#ffffff'), 0.15 * day);
    const az = (hour - 12) / 12 * Math.PI;
    sun.position.set(Math.sin(az) * 60, Math.max(4, el * 70), 30 + Math.cos(az) * 20);
    sunBall.position.set(Math.sin(az) * 170, el * 150, -60); moon.position.set(-Math.sin(az) * 150, -el * 130 + 10, -80);
    sun.intensity = 0.55 + day * 2.0; sun.color.set('#9fb4ff').lerp(new THREE.Color('#fff3d6'), day).lerp(new THREE.Color('#ffb070'), glow * 0.6);
    hemi.intensity = 0.55 + day * 0.5; hemi.color.set('#6f83c4').lerp(new THREE.Color('#dff3ff'), day);
    stars.material.opacity = 1 - day;
    return day;
  }

  const timer = new THREE.Timer(); timer.connect(document); let hoverT = 0;
  renderer.setAnimationLoop(() => {
    timer.update(); const dt = Math.min(timer.getDelta(), 0.1), t = timer.getElapsed();
    const now = new Date();
    const hour = timeMode === 'day' ? 12 : timeMode === 'sunset' ? 18.4 : timeMode === 'night' ? 23 : now.getHours() + now.getMinutes() / 60;
    const day = sky(hour);

    // Gino: walk toward where he says he is
    const d = new THREE.Vector3().subVectors(target, gino.position); d.y = 0;
    const dist = d.length(), walking = dist > 0.08 && !state.asleep;
    if (walking) {
      const step = Math.min(dist, 2.2 * dt); d.normalize(); gino.position.addScaledVector(d, step);
      const want = Math.atan2(-d.z, d.x); let diff = want - gino.rotation.y; diff = Math.atan2(Math.sin(diff), Math.cos(diff)); gino.rotation.y += diff * Math.min(1, dt * 8);
    }
    const inPond = ponds.some(o => Math.hypot(o.position.x - gino.position.x, o.position.z - gino.position.z) < 1.2);
    const gy = groundY(gino.position.x, gino.position.z) + (inPond ? -0.42 : 0);
    gino.position.y += (gy - gino.position.y) * Math.min(1, dt * 6);
    const sleepK = G.sleepK = THREE.MathUtils.lerp(G.sleepK ?? 0, state.asleep ? 1 : 0, Math.min(1, dt * 3));
    G.body.position.y = -0.3 * sleepK + (walking ? Math.abs(Math.sin(t * 9)) * 0.05 : Math.sin(t * 1.6) * 0.012);
    G.body.scale.y = 1 + Math.sin(t * (state.asleep ? 1.1 : 1.8)) * 0.02;
    G.legs.forEach((l, i) => { l.rotation.z = walking ? Math.sin(t * 9 + (i % 3 ? Math.PI : 0)) * 0.6 : 0; l.scale.y = 1 - 0.75 * sleepK; });
    const eating = /munch|eat|forag/.test(state.activity || '') && !state.asleep;
    G.head.rotation.z = -0.35 * sleepK + (eating ? -0.35 + Math.sin(t * 7) * 0.12 : Math.sin(t * 0.7) * 0.05);
    G.head.rotation.y = state.asleep || walking ? 0 : Math.sin(t * 0.4) * 0.35;
    const blink = state.asleep || (t % 4.2) < 0.13; G.eyes.forEach(e => e.scale.y = blink ? 0.015 : 0.1);
    G.ears.forEach((e, i) => e.rotation.x = (Math.sin(t * 2.3 + i) > 0.96 ? 0.5 : 0));
    G.zs.forEach((z, i) => { const k = (t * 0.35 + i / 3) % 1; z.visible = state.asleep; z.position.set(1.0 + k * 0.5, 1.5 + k * 1.3, 0).applyAxisAngle(new THREE.Vector3(0, 1, 0), gino.rotation.y); z.scale.setScalar(0.25 + k * 0.4); z.material.opacity = 1 - k; });

    // living details
    itemsGroup.traverse(n => {
      if (n.userData.water) n.material.opacity = 0.78 + Math.sin(t * 1.5) * 0.05;
      if (n.userData.flame) { n.scale.y = 0.9 + Math.sin(t * 13) * 0.14 + Math.sin(t * 7.3) * 0.08; n.rotation.y = t * 2; }
      if (n.userData.bob) n.position.y = 1.0 + Math.sin(t * 1.4 + n.id) * 0.08;
      if (n.isPointLight) n.intensity = (n.userData.nightLight * (1 - day) + (n.userData.flicker ? 3 : 0)) * (n.userData.flicker ? 0.85 + Math.sin(t * 17) * 0.15 : 1);
    });
    for (const o of itemObjs.values()) if (o.userData.grow) { const s = o.scale.x + (o.userData.grow - o.scale.x) * Math.min(1, dt * 5); o.scale.setScalar(s); if (o.userData.grow - s < 0.002) { o.scale.setScalar(o.userData.grow); o.userData.grow = 0; } }
    clouds.forEach(cl => { cl.position.x += dt * 0.6; if (cl.position.x > 90) cl.position.x = -90; cl.children[0].material.opacity = 0.25 + day * 0.67; });
    flies.forEach(f => { const u = f.userData; u.a += dt * u.s; const x = Math.cos(u.a) * u.r, z = Math.sin(u.a * 1.3) * u.r * 0.7; f.position.set(x, groundY(x, z) + u.h + Math.sin(t * 2 + u.r) * 0.3, z); f.material.color.set('#f6ff9a').lerp(u.c, day); f.material.opacity = day > 0.5 ? 0.9 : 0.4 + Math.abs(Math.sin(t * 2 + u.r)) * 0.6; f.scale.set(day > 0.5 ? 0.16 * Math.abs(Math.sin(t * 12 + u.r)) + 0.03 : 0.09, 0.09, 0.09); });

    if (follow) controls.target.lerp(new THREE.Vector3(gino.position.x, gino.position.y + 0.8, gino.position.z), Math.min(1, dt * 3));
    if (performance.now() > idleAt && !follow) controls.autoRotate = true;
    controls.update();
    renderer.render(scene, camera);
  });

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h; camera.fov = w < 520 ? 55 : 42; camera.updateProjectionMatrix(); renderer.setSize(w, h);
  }
  new ResizeObserver(resize).observe(container); resize();

  // hover / tap to see what a thing is
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  function pick(ev) {
    const r = renderer.domElement.getBoundingClientRect();
    ptr.set((ev.clientX - r.left) / r.width * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, camera);
    const ginoHit = ray.intersectObject(gino, true)[0], hit = ray.intersectObjects(itemsGroup.children, true)[0];
    let text = '';
    if (ginoHit && (!hit || ginoHit.distance < hit.distance)) text = 'Gino' + (state.activity ? ' · ' + state.activity : '');
    else if (hit?.object.userData.item) { const it = hit.object.userData.item; text = `${it.emoji || ''} ${it.name}${it.description ? ' — ' + it.description : ''}`; }
    tooltip.textContent = text; tooltip.style.display = text ? 'block' : 'none';
    tooltip.style.left = Math.min(r.width - 240, Math.max(8, ev.clientX - r.left + 14)) + 'px'; tooltip.style.top = (ev.clientY - r.top + 14) + 'px';
  }
  renderer.domElement.addEventListener('pointermove', ev => { const n = performance.now(); if (n - hoverT > 60) { hoverT = n; pick(ev); } });
  renderer.domElement.addEventListener('pointerleave', () => { tooltip.style.display = 'none'; });

  return {
    update,
    setFollow(v) { follow = v; controls.autoRotate = false; idleAt = v ? Infinity : performance.now() + 20000; if (!v) controls.target.set(0, 0.5, 0); },
    setTime(m) { timeMode = m; },
    _debug: { scene, camera, controls, gino },
  };
}
