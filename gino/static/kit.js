// Modelling kit for Gino's world: every object is built from simple shapes, no model files. three.js r186.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export const U = { time: { value: 0 } };           // shared shader clock
export const env = { season: 'summer', art: [], artKey: '', lite: false };

const mats = new Map();
export function mat(color, extra = {}) {
  const key = color + JSON.stringify(extra);
  if (!mats.has(key)) mats.set(key, new THREE.MeshStandardMaterial({ color, roughness: 0.85, ...extra }));
  return mats.get(key);
}
// Lumpy, smooth-shaded blob with a soft dark-to-light gradient baked in: used for foliage and clouds.
function blob(lump, shade) {
  const g = new THREE.SphereGeometry(0.5, 22, 16), p = g.attributes.position, col = new Float32Array(p.count * 3), v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i); const n = v.clone().normalize();
    const d = 1 + lump * (Math.sin(n.x * 5.1 + n.y * 3.3) * Math.cos(n.z * 4.7 + n.x * 2.1) + 0.5 * Math.sin(n.y * 9.0 + n.z * 7.0) * Math.cos(n.x * 8.0));
    v.copy(n).multiplyScalar(0.5 * d); p.setXYZ(i, v.x, v.y, v.z);
    const k = 1 - shade + shade * (0.5 + n.y * 0.5) * 1.25 + (d - 1) * 0.6; col.set([k, k, k], i * 3);
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.computeVertexNormals(); return g;
}
function faceted(g) { const n = g.index ? g.toNonIndexed() : g; n.computeVertexNormals(); return n; }
export const geos = {
  box: new RoundedBoxGeometry(1, 1, 1, 3, 0.07),
  sphere: new THREE.SphereGeometry(0.5, 18, 12),
  smooth: new THREE.SphereGeometry(0.5, 28, 18),
  leafy: blob(0.16, 0.55),
  puff: blob(0.1, 0.3),
  rock: faceted(new THREE.IcosahedronGeometry(0.5, 1)),
  cyl: new THREE.CylinderGeometry(0.5, 0.5, 1, 20),
  trunk: new THREE.CylinderGeometry(0.36, 0.5, 1, 14),
  cone: new THREE.ConeGeometry(0.5, 1, 18),
  pine: faceted(new THREE.ConeGeometry(0.5, 1, 9)),
  pyramid: faceted(new THREE.ConeGeometry(0.5, 1, 4)),
  disc: new THREE.CylinderGeometry(0.5, 0.5, 1, 40),
  torus: new THREE.TorusGeometry(0.5, 0.18, 12, 28),
  plane: new THREE.PlaneGeometry(1, 1),
};
for (const g of Object.values(geos)) if (!g.attributes.color) g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 3).fill(1), 3));
export function part(parent, geo, color, [sx, sy, sz], [px, py, pz], rot, extra) {
  const m = new THREE.Mesh(geos[geo], color && color.isMaterial ? color : mat(color, extra));
  m.scale.set(sx, sy, sz); m.position.set(px, py, pz);
  if (rot) m.rotation.set(rot[0], rot[1], rot[2]);
  m.castShadow = true; m.receiveShadow = true;
  parent.add(m); return m;
}
export function rng(seed) { let s = (seed * 9301 + 49297) % 233280; return () => (s = (s * 9301 + 49297) % 233280) / 233280; }

// Make a material sway in the wind (grass, leaves) or ripple (water).
export function windy(material, mode = 'sway', amt = 0.18) {
  const amount = amt.toFixed(4);
  material.onBeforeCompile = sh => {
    sh.uniforms.uTime = U.time;
    const body = mode === 'water'
      ? `transformed.z += sin(uTime * 1.3 + position.x * 0.9) * ${amount} + cos(uTime * 1.1 + position.y * 1.1) * ${amount};`
      : `#ifdef USE_INSTANCING
           vec4 wp = instanceMatrix * vec4(0., 0., 0., 1.);
         #else
           vec4 wp = modelMatrix * vec4(0., 0., 0., 1.);
         #endif
         float sw = (sin(uTime * 1.7 + wp.x * 0.35 + wp.z * 0.27) + sin(uTime * 0.6 + wp.x * 0.1) * 0.6) * ${amount} * max(position.y, 0.);
         transformed.x += sw; transformed.z += sw * 0.4;`;
    sh.vertexShader = 'uniform float uTime;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n' + body);
  };
  material.customProgramCacheKey = () => mode + amount;
  return material;
}

const LEAVES = {
  spring: ['#7cc46a', '#8fd07a', '#f5b6d0', '#6fbf5e'],
  summer: ['#4f9a46', '#5da84f', '#468c44', '#6bb257'],
  autumn: ['#e08a2e', '#d4552f', '#e6b93a', '#b9502a', '#9aa83f'],
  winter: ['#dfe8ea', '#cfdcde', '#eef3f4'],
};
export const leaf = r => { const p = LEAVES[env.season] || LEAVES.summer; return p[Math.floor(r() * p.length)]; };
const pineMat = c => { const k = 'pine' + c; if (!mats.has(k)) mats.set(k, windy(new THREE.MeshStandardMaterial({ color: c, roughness: 0.95 }), 'sway', 0.02)); return mats.get(k); };
const leafMat = c => { const k = 'leaf' + c; if (!mats.has(k)) mats.set(k, windy(new THREE.MeshStandardMaterial({ color: c, roughness: 0.95, vertexColors: true }), 'sway', 0.035)); return mats.get(k); };

function emitter(g, n, color, at, opts = {}) {            // smoke, sparks, fountain drops
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(geos.sphere, new THREE.MeshStandardMaterial({ color, transparent: true, roughness: 1, flatShading: true, emissive: opts.emissive || '#000000', emissiveIntensity: opts.glow || 0 }));
    m.userData.puff = { i: i / n, at, rise: opts.rise ?? 1.6, spread: opts.spread ?? 0.35, size: opts.size ?? 0.3, arc: !!opts.arc, speed: opts.speed ?? 0.25 };
    m.castShadow = false; g.add(m);
  }
}
function nightGlow(m, color = '#ffd27a', max = 2.4) {
  m.material = new THREE.MeshStandardMaterial({ color: m.material.color, emissive: color, emissiveIntensity: 0, roughness: 0.6 });
  m.userData.nightGlow = max; m.castShadow = false; return m;
}
function light(g, color, at, night, flicker) {
  const l = new THREE.PointLight(color, 0, 10, 1.5); l.position.set(...at); l.userData.nightLight = night; l.userData.flicker = !!flicker; g.add(l);
}
function artPlane(g, size, pos, rot, slot) {
  const m = new THREE.Mesh(geos.plane, new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.8 }));
  m.scale.set(size[0], size[1], 1); m.position.set(...pos); if (rot) m.rotation.set(...rot);
  m.userData.artSlot = slot; g.add(m); return m;
}

// Water: glossy, reflects the sky, with ripples from a generated normal map that the world scrolls.
let _water = null, _ripples = null;
export function ripples() {
  if (_ripples) return _ripples;
  const N = 256, c = document.createElement('canvas'); c.width = c.height = N;
  const x = c.getContext('2d'), img = x.createImageData(N, N), T = Math.PI * 2 / N;
  const h = (i, j) => Math.sin(i * T * 3 + Math.sin(j * T * 2) * 1.5) + Math.sin(j * T * 5 + Math.cos(i * T * 3) * 1.2) * 0.6 + Math.sin((i + j) * T * 9) * 0.3 + Math.sin((i - j) * T * 14) * 0.15;
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
    const dx = (h(i + 1, j) - h(i - 1, j)) * 0.9, dy = (h(i, j + 1) - h(i, j - 1)) * 0.9, l = Math.hypot(dx, dy, 1), k = (j * N + i) * 4;
    img.data[k] = (-dx / l * 0.5 + 0.5) * 255; img.data[k + 1] = (-dy / l * 0.5 + 0.5) * 255; img.data[k + 2] = (1 / l * 0.5 + 0.5) * 255; img.data[k + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  _ripples = new THREE.CanvasTexture(c); _ripples.wrapS = _ripples.wrapT = THREE.RepeatWrapping; _ripples.repeat.set(3, 3);
  return _ripples;
}
export function waterMat() {
  if (!_water) _water = new THREE.MeshStandardMaterial({ color: '#2f86b8', transparent: true, opacity: 0.88, roughness: 0.05, metalness: 0.1, normalMap: ripples(), normalScale: new THREE.Vector2(0.35, 0.35), envMapIntensity: 1.6 });
  return _water;
}

// ---------------------------------------------------------------- everything Gino can build

// ---- lifelike shapes: sculpted forms and hand-drawn surface textures (still no model files) ----
const sq = (t, e) => Math.sign(t) * Math.pow(Math.abs(t), e);
function sculpt(fn, ws = 44, hs = 30) {
  const g = new THREE.SphereGeometry(1, ws, hs), p = g.attributes.position, col = new Float32Array(p.count * 3), v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i).normalize(); const k = fn(v) ?? 1; p.setXYZ(i, v.x, v.y, v.z); col.set([k, k, k], i * 3); }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.computeVertexNormals(); return g;
}
function canvasTex(size, draw, rx = 1, ry = 1) {
  const c = document.createElement('canvas'); c.width = c.height = size; draw(c.getContext('2d'), size);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
const texCache = {};
const tex = (k, mk) => texCache[k] || (texCache[k] = mk());
const furTex = () => tex('fur', () => canvasTex(512, (x, n) => {
  const r = rng(7); x.fillStyle = '#cfcfcf'; x.fillRect(0, 0, n, n);
  for (let i = 0; i < 16000; i++) { const px = r() * n, py = r() * n, l = 8 + r() * 16, a = (r() - 0.5) * 0.7 + Math.PI / 2, v = 120 + Math.floor(r() * 135);
    x.strokeStyle = `rgba(${v},${v},${v},0.55)`; x.lineWidth = 0.8 + r() * 1.2; x.beginPath(); x.moveTo(px, py); x.lineTo(px + Math.cos(a) * l, py + Math.sin(a) * l); x.stroke(); }
}, 5, 3));
const barkTex = () => tex('bark', () => canvasTex(256, (x, n) => {
  const r = rng(3); x.fillStyle = '#d6d6d6'; x.fillRect(0, 0, n, n);
  for (let i = 0; i < 500; i++) { const px = r() * n, py = r() * n, l = 20 + r() * 70, v = 130 + Math.floor(r() * 110);
    x.strokeStyle = `rgba(${v},${v},${v},0.6)`; x.lineWidth = 1 + r() * 3; x.beginPath(); x.moveTo(px, py); x.bezierCurveTo(px + (r() - 0.5) * 8, py + l * 0.3, px + (r() - 0.5) * 8, py + l * 0.6, px + (r() - 0.5) * 6, py + l); x.stroke(); }
}, 3, 2));
const plankTex = () => tex('plank', () => canvasTex(256, (x, n) => {
  const r = rng(11); x.fillStyle = '#f2f2f2'; x.fillRect(0, 0, n, n);
  for (let row = 0; row < 8; row++) { const y0 = row * 32, v = 215 + Math.floor(r() * 40); x.fillStyle = `rgb(${v},${v},${v})`; x.fillRect(0, y0, n, 32);
    for (let i = 0; i < 26; i++) { const yy = y0 + 3 + r() * 26, xx = r() * n, v2 = 150 + Math.floor(r() * 70); x.strokeStyle = `rgba(${v2},${v2},${v2},0.5)`; x.lineWidth = 1; x.beginPath(); x.moveTo(xx, yy); x.lineTo(xx + 30 + r() * 90, yy + (r() - 0.5) * 3); x.stroke(); }
    x.fillStyle = 'rgba(40,30,20,0.55)'; x.fillRect(0, y0, n, 2.5); const bx = r() * n; x.fillRect(bx, y0, 2, 32); }
}, 2, 1));
const shingleTex = () => tex('shingle', () => canvasTex(256, (x, n) => {
  const r = rng(5); x.fillStyle = '#8a8a8a'; x.fillRect(0, 0, n, n);
  for (let row = 0; row < 8; row++) for (let c = -1; c < 8; c++) { const w = 32, x0 = c * w + (row % 2 ? 16 : 0), y0 = row * 32, v = 170 + Math.floor(r() * 85);
    x.fillStyle = `rgb(${v},${v},${v})`; x.beginPath(); x.moveTo(x0 + 1, y0); x.lineTo(x0 + w - 1, y0); x.lineTo(x0 + w - 1, y0 + 22); x.quadraticCurveTo(x0 + w / 2, y0 + 36, x0 + 1, y0 + 22); x.closePath(); x.fill();
    x.strokeStyle = 'rgba(30,20,15,0.6)'; x.lineWidth = 1.5; x.stroke(); }
}, 3, 4));
function texMat(key, color, map, extra = {}) {
  const k = 'tx' + key + color; if (!mats.has(k)) mats.set(k, new THREE.MeshStandardMaterial({ color, map, bumpMap: map, bumpScale: 0.6, roughness: 0.95, vertexColors: true, ...extra })); return mats.get(k);
}
const barkMat = () => texMat('bark', '#8a6240', barkTex(), { bumpScale: 0.9 });
function meshOf(parent, geo, material, [sx, sy, sz], [px, py, pz], rot) {
  const m = new THREE.Mesh(geo, material); m.scale.set(sx, sy, sz); m.position.set(px, py, pz); if (rot) m.rotation.set(rot[0], rot[1], rot[2]);
  m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
}
let trunkG = null;
function trunkGeo() { if (trunkG) return trunkG; const pts = [[0.62, 0], [0.42, 0.18], [0.31, 0.5], [0.27, 1.2], [0.24, 2.0], [0.2, 2.7], [0.0, 2.75]].map(([x, y]) => new THREE.Vector2(x, y));
  const g = new THREE.LatheGeometry(new THREE.SplineCurve(pts).getPoints(24), 16), p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const y = p.getY(i), a = Math.atan2(p.getZ(i), p.getX(i)), k = 1 + 0.09 * Math.sin(a * 5 + y * 1.3) * (1.2 - y / 2.75); p.setXYZ(i, p.getX(i) * k + 0.05 * Math.sin(y * 1.6), y, p.getZ(i) * k); }
  g.computeVertexNormals(); g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(p.count * 3).fill(1), 3)); return trunkG = g; }
let firG = null;
function firGeo() {
  if (firG) return firG; const seg = 30, g = new THREE.ConeGeometry(0.5, 1, seg, 5, true), p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i), t = 0.5 - y, k = Math.round((Math.atan2(z, x) / (Math.PI * 2)) * seg), alt = ((k % 2) + 2) % 2;
    const rs = 1 - (0.3 + 0.12 * Math.sin(k * 1.7)) * alt * t; p.setXYZ(i, x * rs, y - (alt ? 0 : 0.2 * t * t) + 0.07 * Math.sin(k * 2.3) * t, z * rs); }
  g.computeVertexNormals(); const c = new Float32Array(p.count * 3); for (let i = 0; i < p.count; i++) { const k = 0.72 + 0.4 * (0.5 - p.getY(i)); c.set([k, k, k], i * 3); } g.setAttribute('color', new THREE.BufferAttribute(c, 3));
  return firG = g;
}
const firMat = c => { const k = 'fir' + c; if (!mats.has(k)) mats.set(k, windy(new THREE.MeshStandardMaterial({ color: c, roughness: 1, side: THREE.DoubleSide, vertexColors: true, flatShading: true }), 'sway', 0.02)); return mats.get(k); };
const shade = (hex, dl, dh = 0) => '#' + new THREE.Color(hex).offsetHSL(dh, 0, dl).getHexString();

// Real fur: thin shells of dotted hair stacked outward from the skin. world.js thins them on slow devices (userData.shell).
const furDots = () => tex('furdots', () => canvasTex(256, (x, n) => { const r = rng(13); x.fillStyle = '#000'; x.fillRect(0, 0, n, n);
  for (let i = 0; i < 5600; i++) { const v = 80 + Math.floor(r() * 175); x.fillStyle = `rgb(${v},${v},${v})`; x.beginPath(); x.arc(r() * n, r() * n, 0.8 + r() * 0.9, 0, 6.3); x.fill(); } }, 10, 7));
function furShells(mesh, color, len = 0.05, n = 14) {
  const sc = mesh.scale, k = len / ((sc.x + sc.y + sc.z) / 3);
  for (let i = 1; i <= n; i++) { const t = i / n, key = `shell${color}${i}${k.toFixed(3)}`;
    if (!mats.has(key)) { const m = new THREE.MeshStandardMaterial({ color: shade(color, -0.07 + t * 0.17), alphaMap: furDots(), alphaTest: 0.1 + t * 0.6, roughness: 1, vertexColors: true });
      const off = (k * t).toFixed(4), droop = (k * t * t * 0.7).toFixed(4);
      m.onBeforeCompile = sh => { sh.vertexShader = sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>\n transformed += normalize(objectNormal) * ${off}; transformed.y -= ${droop};`); };
      m.customProgramCacheKey = () => 'shell' + off; mats.set(key, m); }
    const sh = new THREE.Mesh(mesh.geometry, mats.get(key)); sh.receiveShadow = true; sh.userData.shell = i; mesh.add(sh); }
  return mesh;
}
let leafG = null;
function leafGeo() { if (leafG) return leafG; const sh = new THREE.Shape(); sh.moveTo(0, -0.5); sh.quadraticCurveTo(0.46, -0.12, 0, 0.5); sh.quadraticCurveTo(-0.46, -0.12, 0, -0.5);
  const g = new THREE.ShapeGeometry(sh, 4), p = g.attributes.position; for (let i = 0; i < p.count; i++) p.setZ(i, Math.abs(p.getX(i)) * 0.35);   // slight fold along the midrib
  g.computeVertexNormals(); return leafG = g; }
let leafCardM = null;
const leafCardMat = () => leafCardM || (leafCardM = windy(new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.75, side: THREE.DoubleSide }), 'sway', 0.03));
// Real leaves: one instanced mesh of little folded leaf shapes per tree.
function leaves(g, clusters, base, r, per = 85, big = 1) {
  const inst = new THREE.InstancedMesh(leafGeo(), leafCardMat(), clusters.length * per), o = new THREE.Object3D(), c = new THREE.Color(), v = new THREE.Vector3(); let k = 0;
  for (const [x, y, z, s] of clusters) for (let i = 0; i < per; i++) {
    v.set(r() - 0.5, r() - 0.42, r() - 0.5).normalize(); const rad = s * 0.5 * (0.82 + r() * 0.3);
    o.position.set(x + v.x * rad, y + v.y * rad * 0.85, z + v.z * rad); o.lookAt(o.position.x + v.x + (r() - 0.5) * 1.2, o.position.y + v.y + (r() - 0.5) * 1.2 - 0.3, o.position.z + v.z + (r() - 0.5) * 1.2);
    o.rotateZ(r() * 6.28); o.scale.setScalar((0.14 + r() * 0.12) * big); o.updateMatrix(); inst.setMatrixAt(k, o.matrix);
    c.set(base).offsetHSL((r() - 0.5) * 0.05, (r() - 0.5) * 0.1, (r() - 0.5) * 0.16 + v.y * 0.06); inst.setColorAt(k++, c); }
  inst.castShadow = true; inst.receiveShadow = true; g.add(inst); return inst;
}
const brickTex = () => tex('brick', () => canvasTex(128, (x, n) => { const r = rng(21); x.fillStyle = '#6a625a'; x.fillRect(0, 0, n, n);
  for (let row = 0; row < 8; row++) for (let c = -1; c < 4; c++) { const v = 150 + Math.floor(r() * 100); x.fillStyle = `rgb(${v},${v - 8},${v - 14})`; x.fillRect(c * 32 + (row % 2 ? 16 : 0) + 1.5, row * 16 + 1.5, 29, 13); } }, 1, 2));

export const B = {
  tree(g, o, r) {
    const bark = barkMat();
    meshOf(g, trunkGeo(), bark, [1, 1, 1], [0, 0, 0]);
    for (let i = 0; i < 5; i++) { const a = i * 1.257 + r() * 0.5, t = 0.75 + r() * 0.3, l = 1.1 + r() * 0.5;
      meshOf(g, geos.trunk, bark, [0.17, l, 0.17], [Math.cos(a) * 0.45, 2.35 + r() * 0.3, Math.sin(a) * 0.45], [Math.sin(a) * t, 0, -Math.cos(a) * t]); }
    const base = o.color || leaf(r), cl = [], far = o.far || env.lite;      // far: scenery trees on the hills get a lighter crown
    for (let i = 0; i < (far ? 16 : 30); i++) { const a = r() * 6.283, e = (r() - 0.25) * 1.5, rad = 0.7 + r() * 0.8, s = 0.6 + r() * 0.6;
      const x = Math.cos(a) * Math.cos(e) * rad * 1.25, y = 3.05 + Math.sin(e) * rad * 0.95, z = Math.sin(a) * Math.cos(e) * rad * 1.25;
      part(g, 'leafy', leafMat(shade(base, -0.1 + (y - 3.1) * 0.03)), [s * (far ? 1.0 : 0.74), s * (far ? 0.82 : 0.6), s * (far ? 1.0 : 0.74)], [x, y, z], [r() * 3, r() * 6, r() * 3]); cl.push([x, y, z, s]); }
    leaves(g, cl, base, r, far ? 26 : 150, far ? 2.6 : 1);
    for (let i = 0; i < 4; i++) { const a = r() * 6.28; meshOf(g, geos.trunk, bark, [0.07, 0.9, 0.07], [Math.cos(a) * 1.0, 2.75, Math.sin(a) * 1.0], [Math.sin(a) * 1.25, 0, -Math.cos(a) * 1.25]); }
  },
  fruit_tree(g, o, r) {
    B.tree(g, { color: env.season === 'winter' ? null : '#4f9446' }, r);
    const fc = o.color || (/apple|cherry/.test(o.name) ? '#d9463e' : /lemon|banana/.test(o.name) ? '#f2d64b' : /plum|berry/.test(o.name) ? '#8a4fc9' : '#f39a2e');
    for (let i = 0; i < 11; i++) { const a = r() * 6.28, h = 1.8 + r() * 1.5; part(g, 'smooth', fc, [0.24, 0.24, 0.24], [Math.cos(a) * 1.0, h, Math.sin(a) * 1.0], null, { flatShading: false, roughness: 0.5 }); }
  },
  pine(g, o) {
    meshOf(g, geos.trunk, barkMat(), [0.6, 0.3, 0.6], [0, 0.15, 0]);
    meshOf(g, geos.trunk, barkMat(), [0.34, 2.6, 0.34], [0, 1.3, 0]);
    const base = o.color || (env.season === 'winter' ? '#5f8f7a' : '#2b5c3c'), n = o.far || env.lite ? 9 : 14;
    meshOf(g, geos.cone, mat('#1f3f2b'), [1.5, 5.4, 1.5], [0, 3.6, 0]);
    for (let i = 0; i < n; i++) { const t = i / (n - 1), w = 2.9 * (1 - t * 0.88), h = 1.0 - t * 0.3;
      meshOf(g, firGeo(), firMat(shade(base, -0.03 + t * 0.07)), [w, h * (14 / n), w], [0, 1.15 + i * 0.36 * (13 / (n - 1)), 0], [0, i * 0.73, 0]); }
    if (env.season === 'winter') for (const [s, y] of [[1.2, 2.75], [0.85, 3.6], [0.45, 4.6]]) part(g, 'pine', '#f4f8fa', [s, 0.5, s], [0, y, 0]);
  },
  bush(g, o, r) {
    const c = () => leafMat(o.color || leaf(r));
    part(g, 'leafy', c(), [1.1, 0.8, 1.0], [0, 0.35, 0]); part(g, 'leafy', c(), [0.8, 0.6, 0.8], [0.55, 0.3, 0.2]); part(g, 'leafy', c(), [0.7, 0.6, 0.7], [-0.5, 0.28, -0.2]);
    if (/berry/.test(o.name)) for (let i = 0; i < 8; i++) part(g, 'sphere', '#c9365a', [0.12, 0.12, 0.12], [(r() - 0.5) * 1.2, 0.3 + r() * 0.4, (r() - 0.5) * 1.0]);
  },
  flowers(g, o, r) {
    const sun = /sunflower/.test(o.name);
    const cols = o.color ? [o.color] : sun ? ['#f6c833'] : ['#f27ca0', '#f6c833', '#ffffff', '#b78cf0', '#f2603d', '#7ab8f5'];
    const stem = leafMat('#4d9a45');
    for (let i = 0; i < (sun ? 7 : 14); i++) {
      const x = (r() - 0.5) * 1.7, z = (r() - 0.5) * 1.7, h = sun ? 1.1 + r() * 0.7 : 0.3 + r() * 0.35;
      const f = new THREE.Group(); f.position.set(x, 0, z); g.add(f);
      part(f, 'cyl', stem, [0.05, h, 0.05], [0, h / 2, 0]);
      part(f, 'sphere', cols[Math.floor(r() * cols.length)], sun ? [0.46, 0.46, 0.12] : [0.2, 0.16, 0.2], [0, h, 0]);
      part(f, 'sphere', sun ? '#6b4423' : '#f6e27a', sun ? [0.22, 0.22, 0.16] : [0.09, 0.1, 0.09], [0, h + (sun ? 0 : 0.06), 0]);
      f.userData.wobble = r() * 6;
    }
  },
  mushroom(g, o) {
    for (const [x, z, s] of [[0, 0, 1], [0.5, 0.3, 0.6], [-0.4, 0.4, 0.45], [0.1, -0.5, 0.35]]) {
      part(g, 'cyl', '#f4ead8', [0.22 * s, 0.6 * s, 0.22 * s], [x, 0.3 * s, z]);
      part(g, 'sphere', o.color || '#d9463e', [0.9 * s, 0.5 * s, 0.9 * s], [x, 0.65 * s, z]);
      for (let i = 0; i < 4; i++) part(g, 'sphere', '#ffffff', [0.12 * s, 0.06 * s, 0.12 * s], [x + Math.cos(i * 1.7) * 0.25 * s, 0.86 * s, z + Math.sin(i * 1.7) * 0.25 * s]);
    }
  },
  rock(g, o, r) {
    const c = o.color || '#9b978f';
    part(g, 'rock', c, [1.3, 0.9, 1.1], [0, 0.35, 0], [r(), r(), r()]);
    part(g, 'rock', c, [0.7, 0.5, 0.6], [0.7, 0.2, 0.3], [r(), r(), r()]);
    part(g, 'sphere', '#6f9a58', [0.6, 0.12, 0.5], [-0.1, 0.78, 0]);
  },
  pond(g, o, r) {
    const wm = o.color ? new THREE.MeshStandardMaterial({ color: o.color, transparent: true, opacity: 0.85, roughness: 0.08 }) : waterMat();
    const w = part(g, 'disc', wm, [3.6, 0.06, 3.0], [0, 0.05, 0]); w.castShadow = false; w.userData.water = true;
    part(g, 'disc', '#2f7ea8', [2.8, 0.05, 2.3], [0, 0.03, 0]).castShadow = false;
    part(g, 'disc', '#d9c9a0', [4.1, 0.04, 3.5], [0, 0.0, 0]).castShadow = false;
    for (let i = 0; i < 13; i++) { const a = i / 13 * 6.28 + r() * 0.3, s = 0.25 + r() * 0.35; part(g, 'rock', '#9a968c', [s, s * 0.6, s], [Math.cos(a) * 1.85, 0.08, Math.sin(a) * 1.55], [r(), r(), 0]); }
    for (let i = 0; i < 4; i++) { const a = r() * 6.28, d = r() * 1.0, x = Math.cos(a) * d, z = Math.sin(a) * d; part(g, 'disc', '#6bbf59', [0.42, 0.03, 0.42], [x, 0.09, z]).castShadow = false; if (i < 2) part(g, 'sphere', '#f7b3cf', [0.16, 0.12, 0.16], [x, 0.14, z]); }
    for (let i = 0; i < 6; i++) { const a = r() * 6.28; const m = part(g, 'cyl', leafMat('#7fae52'), [0.05, 1.0, 0.05], [Math.cos(a) * 1.7, 0.5, Math.sin(a) * 1.4]); part(g, 'cyl', '#6b4423', [0.09, 0.25, 0.09], [m.position.x, 1.0, m.position.z]); }
  },
  fountain(g, o) {
    part(g, 'disc', '#bdb7ab', [2.2, 0.35, 2.2], [0, 0.17, 0]);
    const w = part(g, 'disc', waterMat(), [1.9, 0.1, 1.9], [0, 0.32, 0]); w.castShadow = false;
    part(g, 'cyl', '#bdb7ab', [0.3, 1.0, 0.3], [0, 0.7, 0]); part(g, 'disc', '#cfc9bd', [0.8, 0.12, 0.8], [0, 1.2, 0]);
    emitter(g, 10, o.color || '#bfe6fb', [0, 1.3, 0], { rise: 0.9, spread: 0.7, size: 0.11, arc: true, speed: 0.6 });
  },
  well(g, o) {
    part(g, 'cyl', '#a9a399', [1.2, 0.7, 1.2], [0, 0.35, 0]); part(g, 'disc', waterMat(), [0.95, 0.05, 0.95], [0, 0.69, 0]);
    for (const x of [-0.55, 0.55]) part(g, 'box', '#7a5230', [0.1, 1.5, 0.1], [x, 1.2, 0]);
    part(g, 'pyramid', o.color || '#b5553c', [1.9, 0.6, 1.9], [0, 2.2, 0], [0, Math.PI / 4, 0]);
    part(g, 'cyl', '#7a5230', [0.08, 1.1, 0.08], [0, 1.75, 0], [0, 0, Math.PI / 2]); part(g, 'cyl', '#8d6a45', [0.25, 0.28, 0.25], [0, 1.2, 0]);
  },
  garden(g, o, r) {
    part(g, 'box', '#8a6642', [2.0, 0.22, 2.0], [0, 0.11, 0]); part(g, 'box', '#5a3d26', [1.8, 0.24, 1.8], [0, 0.12, 0]);
    const veg = ['#f08a2c', '#e0503d', '#f2c14e', '#8fce5b', '#b565c9'];
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      part(g, 'cone', leafMat('#58a84a'), [0.32, 0.45, 0.32], [i * 0.55, 0.42, j * 0.55]);
      part(g, 'sphere', veg[Math.floor(r() * veg.length)], [0.2, 0.2, 0.2], [i * 0.55 + 0.12, 0.3, j * 0.55 + 0.08]);
    }
    part(g, 'box', '#8a6642', [0.08, 0.9, 0.08], [0.95, 0.45, -0.95]); part(g, 'box', '#e8d3a8', [0.4, 0.25, 0.04], [0.95, 0.85, -0.92]);
  },
  pumpkins(g, o, r) {
    for (let i = 0; i < 5; i++) { const s = 0.4 + r() * 0.45, x = (r() - 0.5) * 1.5, z = (r() - 0.5) * 1.5; part(g, 'sphere', o.color || '#ee8a2a', [s, s * 0.75, s], [x, s * 0.36, z]); part(g, 'cyl', '#5d7d32', [0.06, 0.16, 0.06], [x, s * 0.76, z]); }
    for (let i = 0; i < 5; i++) part(g, 'sphere', leafMat('#4f9446'), [0.4, 0.06, 0.3], [(r() - 0.5) * 1.7, 0.05, (r() - 0.5) * 1.7], [0, r() * 3, 0]);
  },
  beehive(g, o) {
    part(g, 'box', '#8a6642', [0.9, 0.5, 0.9], [0, 0.25, 0]);
    for (let i = 0; i < 4; i++) part(g, 'disc', o.color || '#eab54a', [0.85 - i * 0.14, 0.24, 0.85 - i * 0.14], [0, 0.62 + i * 0.22, 0]);
    part(g, 'smooth', '#3d2a18', [0.16, 0.16, 0.06], [0, 0.7, 0.42]);
    emitter(g, 4, '#f6d23c', [0, 1.3, 0], { rise: 0.2, spread: 1.4, size: 0.07, speed: 0.5 });
  },
  bed(g, o) {
    part(g, 'torus', o.color || '#e3c878', [1.8, 1.8, 1.4], [0, 0.2, 0], [Math.PI / 2, 0, 0]);
    part(g, 'disc', '#f1dc9c', [1.6, 0.18, 1.6], [0, 0.1, 0]);
    part(g, 'smooth', '#f7efe2', [0.7, 0.28, 0.45], [-0.4, 0.3, 0], null, { flatShading: false }); part(g, 'box', '#9fc3e8', [0.9, 0.06, 1.0], [0.3, 0.22, 0], [0, 0.2, 0]);
  },
  hammock(g, o) {
    part(g, 'cyl', '#7a5230', [0.14, 1.7, 0.14], [-1.2, 0.85, 0], [0, 0, 0.12]); part(g, 'cyl', '#7a5230', [0.14, 1.7, 0.14], [1.2, 0.85, 0], [0, 0, -0.12]);
    const c = o.color || '#e0705a', sw = new THREE.Group(); sw.position.y = 1.5; sw.userData.swing = 0.12; g.add(sw);
    for (let i = -4; i <= 4; i++) part(sw, 'box', i % 2 ? c : '#f6e9d2', [0.27, 0.05, 0.8], [i * 0.26, -0.75 + i * i * 0.045, 0], [0, 0, -i * 0.09]);
  },
  swing(g, o) {
    for (const x of [-0.9, 0.9]) { part(g, 'box', '#7a5230', [0.12, 2.4, 0.12], [x, 1.2, 0.35], [0.28, 0, 0]); part(g, 'box', '#7a5230', [0.12, 2.4, 0.12], [x, 1.2, -0.35], [-0.28, 0, 0]); }
    part(g, 'box', '#7a5230', [2.0, 0.12, 0.12], [0, 2.3, 0]);
    const sw = new THREE.Group(); sw.position.y = 2.3; sw.userData.swing = 0.35; sw.userData.axis = 'x'; g.add(sw);
    for (const x of [-0.3, 0.3]) part(sw, 'cyl', '#d8cfc0', [0.03, 1.6, 0.03], [x, -0.8, 0]);
    part(sw, 'box', o.color || '#e0705a', [0.8, 0.07, 0.35], [0, -1.6, 0]);
  },
  bench(g, o) {
    part(g, 'box', o.color || '#a87645', [1.6, 0.1, 0.5], [0, 0.5, 0]); part(g, 'box', o.color || '#a87645', [1.6, 0.5, 0.08], [0, 0.85, -0.22], [-0.12, 0, 0]);
    for (const x of [-0.65, 0.65]) part(g, 'box', '#5a5a60', [0.1, 0.5, 0.45], [x, 0.25, 0]);
  },
  table(g, o) {
    part(g, 'disc', o.color || '#b98d5a', [1.4, 0.1, 1.4], [0, 0.7, 0]); part(g, 'cyl', '#8a6642', [0.2, 0.7, 0.2], [0, 0.35, 0]);
    part(g, 'disc', '#f4ead8', [0.4, 0.04, 0.4], [0.25, 0.77, 0.1]); part(g, 'smooth', '#e0503d', [0.18, 0.18, 0.18], [0.25, 0.86, 0.1], null, { flatShading: false });
  },
  picnic(g, o) {
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) part(g, 'box', (i + j) % 2 ? (o.color || '#e0503d') : '#fbf7ee', [0.5, 0.03, 0.5], [(i - 1.5) * 0.5, 0.03, (j - 1.5) * 0.5]).castShadow = false;
    part(g, 'box', '#b98d5a', [0.6, 0.35, 0.4], [0.3, 0.2, 0.2]); part(g, 'torus', '#8a6642', [0.5, 0.5, 0.3], [0.3, 0.4, 0.2]);
    part(g, 'sphere', '#4f9446', [0.5, 0.42, 0.42], [-0.45, 0.24, -0.3]); part(g, 'smooth', '#f39a2e', [0.2, 0.2, 0.2], [-0.2, 0.13, 0.5], null, { flatShading: false });
  },
  bookshelf(g, o, r) {
    part(g, 'box', o.color || '#9a6b3f', [1.5, 1.8, 0.45], [0, 0.9, 0]);
    const cols = ['#d9534f', '#4f8bd9', '#58b368', '#e8b84a', '#9a6fd1', '#e88a4a'];
    for (let row = 0; row < 3; row++) {
      part(g, 'box', '#3d2a18', [1.34, 0.46, 0.1], [0, 0.35 + row * 0.56, 0.2]);
      for (let i = 0; i < 7; i++) part(g, 'box', cols[Math.floor(r() * 6)], [0.14, 0.3 + r() * 0.12, 0.2], [-0.54 + i * 0.18, 0.3 + row * 0.56, 0.24], [0, 0, r() < 0.15 ? 0.2 : 0]);
    }
  },
  easel(g, o) {
    for (const [x, rz] of [[-0.35, 0.2], [0.35, -0.2]]) part(g, 'box', '#8a6642', [0.07, 1.6, 0.07], [x, 0.8, 0], [0.15, 0, rz]);
    part(g, 'box', '#8a6642', [0.07, 1.5, 0.07], [0, 0.75, -0.35], [-0.3, 0, 0]);
    part(g, 'box', '#fbf7ee', [1.0, 1.0, 0.05], [0, 1.1, 0.07], [-0.15, 0, 0]);
    artPlane(g, [0.9, 0.9], [0, 1.1, 0.105], [-0.15, 0, 0], 0);
  },
  gallery(g, o) {
    part(g, 'box', o.color || '#8a6642', [3.4, 1.6, 0.14], [0, 1.3, 0]);
    for (const x of [-1.5, 1.5]) part(g, 'box', '#6b4a2f', [0.16, 2.2, 0.16], [x, 1.1, 0]);
    part(g, 'box', '#b5553c', [3.7, 0.12, 0.5], [0, 2.2, 0]);
    for (let i = 0; i < 3; i++) { part(g, 'box', '#f4ead8', [0.98, 0.98, 0.04], [(i - 1) * 1.08, 1.3, 0.08]); artPlane(g, [0.88, 0.88], [(i - 1) * 1.08, 1.3, 0.105], null, i); }
  },
  statue(g, o) {
    part(g, 'box', '#b9b4aa', [1.0, 0.35, 0.8], [0, 0.17, 0]);
    const c = o.color || '#cfc9bd';       // a little capybara statue, naturally
    part(g, 'smooth', c, [1.0, 0.62, 0.6], [0, 0.7, 0], null, { flatShading: false }); part(g, 'smooth', c, [0.5, 0.42, 0.42], [0.5, 0.95, 0], null, { flatShading: false });
    part(g, 'box', c, [0.3, 0.26, 0.3], [0.72, 0.9, 0]);
  },
  sign(g, o) {
    part(g, 'box', '#8a6642', [0.1, 1.1, 0.1], [0, 0.55, 0]); part(g, 'box', o.color || '#e8d3a8', [0.95, 0.5, 0.08], [0, 1.05, 0.04]);
    for (let i = 0; i < 3; i++) part(g, 'box', '#6b4a2f', [0.6 - i * 0.12, 0.04, 0.02], [0, 1.17 - i * 0.12, 0.09]);
  },
  capsule(g, o) {   // a time capsule: a little mound of fresh earth with a marker stake; dug up, an open tin
    const opened = /opened/.test(o.name);
    part(g, 'smooth', '#7a5a3a', [1.5, 0.42, 1.3], [0, 0.04, 0]); part(g, 'smooth', '#8d6b47', [0.95, 0.3, 0.85], [0.08, 0.16, -0.05]);
    for (let i = 0; i < 5; i++) part(g, 'rock', '#9b978f', [0.16, 0.12, 0.14], [Math.cos(i * 1.3) * 0.72, 0.08, Math.sin(i * 1.3) * 0.6], [i, i * 2, 0]);
    part(g, 'box', '#a07a4f', [0.08, 1.15, 0.08], [0.42, 0.62, 0.12]);
    part(g, 'box', o.color || '#e0705a', [0.34, 0.2, 0.03], [0.6, 1.02, 0.12]);
    if (opened) {
      part(g, 'cyl', '#c9b27a', [0.42, 0.34, 0.42], [-0.42, 0.3, 0.3], null, { metalness: 0.5, roughness: 0.4 });
      part(g, 'cyl', '#d8c58c', [0.46, 0.05, 0.46], [-0.82, 0.2, 0.56], [0.25, 0, 1.25], { metalness: 0.5, roughness: 0.4 });
      part(g, 'box', '#f6efdc', [0.32, 0.02, 0.24], [-0.4, 0.5, 0.3], [0.25, 0.5, 0]);
    } else part(g, 'smooth', '#f6c833', [0.13, 0.13, 0.13], [0.42, 1.22, 0.12], null, { emissive: '#f6c833', emissiveIntensity: 0.6 });
  },
  mailbox(g, o) {
    part(g, 'box', '#8a6642', [0.1, 1.0, 0.1], [0, 0.5, 0]); part(g, 'box', o.color || '#d9534f', [0.6, 0.35, 0.35], [0, 1.1, 0]);
    part(g, 'cyl', o.color || '#d9534f', [0.35, 0.6, 0.35], [0, 1.27, 0], [0, 0, Math.PI / 2]); part(g, 'box', '#f6c833', [0.04, 0.3, 0.12], [0.2, 1.35, 0.2]);
  },
  flag(g, o) {
    part(g, 'cyl', '#d8d3c8', [0.07, 3.0, 0.07], [0, 1.5, 0]); part(g, 'smooth', '#f6c833', [0.16, 0.16, 0.16], [0, 3.02, 0]);
    const fm = windy(new THREE.MeshStandardMaterial({ color: o.color || '#e0705a', side: THREE.DoubleSide, roughness: 0.8 }), 'water', 0.07);
    const f = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.7, 10, 4), fm); f.position.set(0.63, 2.55, 0); f.castShadow = true; g.add(f);
  },
  fence(g, o) {
    const c = o.color || '#b98d5a';
    for (let i = -2; i <= 2; i++) { part(g, 'box', c, [0.12, 0.8, 0.12], [i * 0.45, 0.4, 0]); part(g, 'pyramid', c, [0.17, 0.14, 0.17], [i * 0.45, 0.87, 0], [0, Math.PI / 4, 0]); }
    part(g, 'box', c, [1.95, 0.1, 0.07], [0, 0.6, 0]); part(g, 'box', c, [1.95, 0.1, 0.07], [0, 0.3, 0]);
  },
  path(g, o, r) {
    for (let i = 0; i < 6; i++) part(g, 'disc', o.color || '#b8b2a6', [0.5 + r() * 0.3, 0.06, 0.45 + r() * 0.25], [(i % 3 - 1) * 0.62 + (r() - 0.5) * 0.2, 0.03, (Math.floor(i / 3) - 0.5) * 0.8 + (r() - 0.5) * 0.2], [0, r() * 3, 0]).castShadow = false;
  },
  bridge(g, o) {
    const c = o.color || '#a87645';
    for (let i = -4; i <= 4; i++) part(g, 'box', c, [0.3, 0.08, 1.1], [i * 0.3, 0.55 - i * i * 0.03, 0], [0, 0, -i * 0.06]);
    for (const z of [-0.5, 0.5]) { for (const x of [-1.2, 0, 1.2]) part(g, 'box', '#7a5230', [0.09, 0.6, 0.09], [x, 0.75 - x * x * 0.3, z]); part(g, 'box', '#7a5230', [2.5, 0.07, 0.07], [0, 0.95, z]); }
  },
  arch(g, o, r) {
    const c = o.color || '#c9c2b4';
    for (const x of [-0.8, 0.8]) part(g, 'box', c, [0.35, 1.8, 0.35], [x, 0.9, 0]);
    for (let i = 0; i <= 6; i++) { const a = i / 6 * Math.PI; part(g, 'box', c, [0.36, 0.36, 0.36], [Math.cos(a) * 0.8, 1.8 + Math.sin(a) * 0.6, 0], [0, 0, a]); }
    for (let i = 0; i < 7; i++) { const a = i / 6 * Math.PI; part(g, 'leafy', leafMat(leaf(r)), [0.5, 0.4, 0.55], [Math.cos(a) * 0.85, 1.85 + Math.sin(a) * 0.72, 0.1]); }
  },
  lamp(g, o) {
    part(g, 'cyl', '#3f3f47', [0.1, 1.9, 0.1], [0, 0.95, 0]); part(g, 'cyl', '#3f3f47', [0.3, 0.1, 0.3], [0, 0.05, 0]);
    part(g, 'pyramid', '#3f3f47', [0.55, 0.22, 0.55], [0, 2.22, 0], [0, Math.PI / 4, 0]);
    nightGlow(part(g, 'smooth', '#fff3cf', [0.34, 0.36, 0.34], [0, 1.95, 0]), o.color || '#ffcf66', 4);
    light(g, o.color || '#ffcf66', [0, 1.95, 0], 16);
  },
  campfire(g, o) {
    for (let i = 0; i < 8; i++) { const a = i / 8 * 6.28; part(g, 'rock', '#8d8a84', [0.3, 0.22, 0.3], [Math.cos(a) * 0.62, 0.08, Math.sin(a) * 0.62]); }
    for (let i = 0; i < 3; i++) part(g, 'cyl', '#5a3a20', [0.13, 0.95, 0.13], [0, 0.22, 0], [1.1, i * 2.1, 0]);
    for (const [s, h, c, e] of [[0.55, 0.95, '#ff8a2c', '#ff5a00'], [0.32, 0.65, '#ffd24a', '#ffb000']]) { const f = part(g, 'cone', c, [s, h, s], [0, 0.3 + h / 2, 0], null, { emissive: e, emissiveIntensity: 2.6, transparent: true, opacity: 0.92 }); f.castShadow = false; f.userData.flame = h; }
    emitter(g, 6, '#ffb347', [0, 0.9, 0], { rise: 2.2, spread: 0.5, size: 0.06, emissive: '#ff8a00', glow: 3, speed: 0.5 });
    emitter(g, 4, '#8a8a8a', [0, 1.2, 0], { rise: 2.6, spread: 0.5, size: 0.4, speed: 0.16 });
    light(g, '#ff8a3c', [0, 0.9, 0], 18, true);
  },
  house(g, o) {
    const wall = o.color || '#e8d3b0', wood = '#5d3f27', wm = texMat('plank', wall, plankTex()), roof = texMat('shingle', '#b5553c', shingleTex(), { bumpScale: 1.2 });
    part(g, 'box', '#8b867f', [2.32, 0.3, 2.02], [0, 0.15, 0]);                                        // stone footing
    for (let i = 0; i < 9; i++) part(g, 'rock', i % 2 ? '#9a958d' : '#7d7871', [0.34, 0.26, 0.2], [-1.0 + i * 0.25, 0.14, 1.0], [0, i, 0]);
    meshOf(g, geos.box, wm, [2.1, 1.4, 1.8], [0, 0.98, 0]);
    const tri = new THREE.Shape(); tri.moveTo(-1.05, 0); tri.lineTo(1.05, 0); tri.lineTo(0, 0.8); tri.closePath();
    const gable = new THREE.ExtrudeGeometry(tri, { depth: 1.78, bevelEnabled: false }); gable.translate(0, 0, -0.89);
    const gm = new THREE.Mesh(gable, mat(shade(wall, -0.04))); gm.position.y = 1.66; gm.castShadow = true; g.add(gm);
    for (const sgn of [-1, 1]) { const sl = meshOf(g, geos.box, roof, [1.95, 0.12, 2.5], [sgn * 0.74, 2.1, 0], [0, 0, -sgn * 0.643]); sl.material.map.rotation = Math.PI / 2; }
    part(g, 'box', wood, [0.16, 0.14, 2.6], [0, 2.62, 0]);                                              // ridge beam
    for (const z of [-1.24, 1.24]) for (const sgn of [-1, 1]) part(g, 'box', wood, [1.95, 0.1, 0.08], [sgn * 0.74, 2.04, z], [0, 0, -sgn * 0.643]);   // barge boards
    for (const [x, z] of [[-1.05, 0.9], [1.05, 0.9], [-1.05, -0.9], [1.05, -0.9]]) part(g, 'box', wood, [0.12, 1.42, 0.12], [x, 0.98, z]);            // corner posts
    meshOf(g, geos.box, texMat('brick', '#b08a78', brickTex(), { bumpScale: 1.5 }), [0.4, 1.15, 0.4], [0.62, 2.45, -0.35]); part(g, 'box', '#6f6c67', [0.46, 0.1, 0.46], [0.62, 3.03, -0.35]);
    part(g, 'box', '#6b4a2f', [0.56, 1.0, 0.07], [0, 0.8, 0.91]); part(g, 'box', wood, [0.7, 0.09, 0.1], [0, 1.33, 0.92]);
    for (const sgn of [-1, 1]) part(g, 'box', wood, [0.08, 1.02, 0.1], [sgn * 0.31, 0.8, 0.92]);
    part(g, 'smooth', '#f6c833', [0.08, 0.08, 0.08], [0.17, 0.8, 0.96]); part(g, 'box', '#9a958d', [0.9, 0.12, 0.4], [0, 0.06, 1.15]);
    const winGlow = part(g, 'smooth', '#a9d8ee', [0.3, 0.3, 0.05], [0, 2.02, 0.9]); nightGlow(winGlow, '#ffc76a', 2.6); part(g, 'torus', wood, [0.34, 0.34, 0.2], [0, 2.02, 0.9]);
    for (const p of [[0.68, 1.1, 0.91, 0], [-0.68, 1.1, 0.91, 0], [1.06, 1.1, 0, 1]]) {
      const f = new THREE.Group(); f.position.set(p[0], p[1], p[2]); f.rotation.y = p[3] * Math.PI / 2; g.add(f);
      const w = nightGlow(part(f, 'box', '#a9d8ee', [0.42, 0.46, 0.05], [0, 0, 0]), '#ffc76a', 2.6); w.castShadow = false;
      part(f, 'box', wood, [0.5, 0.05, 0.08], [0, 0.25, 0.02]); part(f, 'box', wood, [0.56, 0.07, 0.14], [0, -0.26, 0.04]);
      for (const sgn of [-1, 1]) part(f, 'box', wood, [0.05, 0.5, 0.08], [sgn * 0.23, 0, 0.02]);
      part(f, 'box', wood, [0.03, 0.46, 0.07], [0, 0, 0.02]); part(f, 'box', wood, [0.42, 0.03, 0.07], [0, 0, 0.02]);
      for (const sgn of [-1, 1]) part(f, 'box', '#3f6b4a', [0.17, 0.5, 0.04], [sgn * 0.35, 0, 0.02]);                                             // shutters
    }
    for (const sgn of [-1, 1]) { part(g, 'box', wood, [0.08, 1.3, 0.08], [sgn * 0.5, 0.78, 1.42]); part(g, 'box', wood, [0.07, 0.07, 0.55], [sgn * 0.5, 1.42, 1.17]); }
    meshOf(g, geos.box, roof, [1.3, 0.08, 0.75], [0, 1.52, 1.22], [0.3, 0, 0]);                         // little porch roof
    for (const dx of [-0.14, 0, 0.14]) part(g, 'box', '#4a321f', [0.012, 0.92, 0.02], [dx, 0.8, 0.95]);
    for (const dy of [0.5, 1.1]) part(g, 'box', '#2b2b2b', [0.3, 0.035, 0.02], [-0.12, dy, 0.955]);
    const lan = part(g, 'box', '#ffd27a', [0.09, 0.13, 0.09], [0.42, 1.2, 0.98]); nightGlow(lan, '#ffc76a', 3); part(g, 'box', '#2b2b2b', [0.12, 0.03, 0.12], [0.42, 1.28, 0.98]);
    for (const x0 of [0.68, -0.68]) { part(g, 'box', '#6b4a2f', [0.52, 0.11, 0.14], [x0, 0.8, 1.0]);
      for (let i = 0; i < 6; i++) { part(g, 'sphere', '#4f9446', [0.1, 0.1, 0.1], [x0 - 0.2 + i * 0.08, 0.88, 1.0]); part(g, 'sphere', ['#e8524f', '#f4c542', '#f6f1e6', '#d96bb0'][i % 4], [0.06, 0.06, 0.06], [x0 - 0.2 + i * 0.08, 0.94 + (i % 2) * 0.02, 1.03]); } }
    for (let i = 0; i < 7; i++) meshOf(g, geos.cyl, barkMat(), [0.15, 0.6, 0.15], [-1.32, 0.1 + Math.floor(i / 4) * 0.14, -0.3 + (i % 4) * 0.16 + (i > 3 ? 0.08 : 0)], [0, 0, Math.PI / 2]);   // wood pile
    part(g, 'box', wood, [0.16, 0.05, 2.62], [0, 2.7, 0]);
    emitter(g, 5, '#d8d8d8', [0.62, 3.1, -0.35], { rise: 2.4, spread: 0.45, size: 0.36, speed: 0.14 });
    light(g, '#ffc76a', [0, 0.9, 1.6], 6);
  },
  tent(g, o) {
    part(g, 'pyramid', o.color || '#e0a04a', [2.4, 1.7, 2.4], [0, 0.85, 0], [0, Math.PI / 4, 0]);
    part(g, 'pyramid', '#3d2a18', [0.9, 1.1, 0.2], [0, 0.55, 0.78], [0, Math.PI / 4, 0]);
    part(g, 'cyl', '#7a5230', [0.05, 0.4, 0.05], [0, 1.85, 0]); part(g, 'pyramid', '#d9534f', [0.3, 0.2, 0.05], [0.14, 1.97, 0]);
  },
  windmill(g, o) {
    part(g, 'cyl', o.color || '#efe6d4', [1.3, 3.0, 1.3], [0, 1.5, 0]).geometry = new THREE.CylinderGeometry(0.34, 0.5, 1, 8);
    part(g, 'cone', '#b5553c', [1.25, 0.8, 1.25], [0, 3.4, 0]); part(g, 'box', '#6b4a2f', [0.4, 0.7, 0.06], [0, 0.35, 0.63]);
    const hub = new THREE.Group(); hub.position.set(0, 2.9, 0.62); hub.userData.spin = 0.7; g.add(hub);
    part(hub, 'cyl', '#6b4a2f', [0.2, 0.25, 0.2], [0, 0, 0], [Math.PI / 2, 0, 0]);
    for (let i = 0; i < 4; i++) { const b = new THREE.Group(); b.rotation.z = i * Math.PI / 2; hub.add(b); part(b, 'box', '#7a5230', [0.07, 1.7, 0.05], [0, 0.85, 0]); part(b, 'box', '#fbf7ee', [0.42, 1.2, 0.03], [0.22, 1.05, 0]); }
  },
  boat(g, o) {
    part(g, 'box', o.color || '#b5553c', [1.9, 0.4, 0.85], [0, 0.25, 0]); part(g, 'pyramid', o.color || '#b5553c', [0.85, 0.7, 0.4], [1.2, 0.25, 0], [0, 0, -Math.PI / 2]);
    part(g, 'box', '#e8d3b0', [1.6, 0.06, 0.6], [0, 0.44, 0]); part(g, 'cyl', '#7a5230', [0.07, 1.8, 0.07], [0.1, 1.3, 0]);
    part(g, 'pyramid', '#fbf7ee', [0.05, 1.4, 1.0], [0.1, 1.45, 0.02]).scale.set(1.1, 1.4, 0.06);
    g.userData.float = true;
  },
  snowman(g, o) {
    for (const [s, y] of [[1.0, 0.45], [0.72, 1.15], [0.5, 1.7]]) part(g, 'smooth', '#f7fafc', [s, s, s], [0, y, 0], null, { flatShading: false });
    part(g, 'cone', '#f08a2c', [0.1, 0.35, 0.1], [0, 1.7, 0.3], [Math.PI / 2, 0, 0]);
    for (const x of [-0.1, 0.1]) part(g, 'smooth', '#1f1711', [0.07, 0.07, 0.07], [x, 1.8, 0.22]);
    part(g, 'cyl', '#2b2b33', [0.45, 0.05, 0.45], [0, 1.93, 0]); part(g, 'cyl', '#2b2b33', [0.3, 0.3, 0.3], [0, 2.08, 0]);
    part(g, 'torus', o.color || '#d9534f', [0.55, 0.55, 0.5], [0, 1.42, 0], [Math.PI / 2, 0, 0]);
  },
  telescope(g, o) {
    for (let i = 0; i < 3; i++) part(g, 'cyl', '#5a5a60', [0.05, 1.3, 0.05], [Math.cos(i * 2.09) * 0.3, 0.6, Math.sin(i * 2.09) * 0.3], [Math.sin(i * 2.09) * 0.45, 0, -Math.cos(i * 2.09) * 0.45]);
    part(g, 'cyl', o.color || '#d9dde6', [0.24, 1.2, 0.24], [0.1, 1.45, 0], [0, 0, -0.9]); part(g, 'cyl', '#3f3f47', [0.28, 0.2, 0.28], [0.52, 1.78, 0], [0, 0, -0.9]);
    part(g, 'cyl', '#3f3f47', [0.12, 0.25, 0.12], [-0.42, 1.04, 0], [0, 0, -0.9]);
  },
  piano(g, o) {
    part(g, 'box', o.color || '#2b2b33', [1.6, 0.9, 0.5], [0, 0.75, -0.1]); part(g, 'box', '#fbf7ee', [1.4, 0.06, 0.3], [0, 0.72, 0.25]);
    for (let i = 0; i < 9; i++) part(g, 'box', '#1f1711', [0.07, 0.05, 0.18], [-0.6 + i * 0.15, 0.76, 0.2]);
    for (const x of [-0.7, 0.7]) part(g, 'box', '#2b2b33', [0.1, 0.7, 0.4], [x, 0.35, 0.1]);
    emitter(g, 3, '#f6c833', [0, 1.5, 0], { rise: 1.2, spread: 0.8, size: 0.1, speed: 0.3, emissive: '#f6c833', glow: 1 });
  },
};
export const KINDS = Object.keys(B);
const KEYWORDS = [
  [/time capsule|capsule/, 'capsule'],
  [/fountain/, 'fountain'], [/\bwell\b/, 'well'], [/pond|pool|lake|water|spring|bath|puddle|onsen/, 'pond'], [/pumpkin/, 'pumpkins'],
  [/garden|vegetable|veggie|crop|farm/, 'garden'], [/hammock/, 'hammock'], [/swing/, 'swing'], [/fire\b|bonfire/, 'campfire'],
  [/\bbed|nest|pillow|cushion|blanket/, 'bed'], [/book|library|shelf/, 'bookshelf'], [/gallery|art wall|museum|exhibit/, 'gallery'],
  [/orange|apple|lemon|fruit|cherry|peach|mango|plum/, 'fruit_tree'], [/\b(pine|fir|spruce)/, 'pine'], [/tree|willow|oak|shade|maple/, 'tree'],
  [/flower|tulip|daisy|rose|lily|blossom|lavender/, 'flowers'], [/rock|stone|boulder|pebble/, 'rock'], [/windmill|mill\b/, 'windmill'],
  [/lamp|lantern|\blight|candle/, 'lamp'], [/tent|tipi|camp\b/, 'tent'], [/house|hut|den\b|cabin|home|shed|burrow|studio|cottage/, 'house'],
  [/fence|gate/, 'fence'], [/bridge/, 'bridge'], [/arch|gateway|portal/, 'arch'], [/picnic/, 'picnic'], [/bench|seat|chair|sofa/, 'bench'],
  [/table|desk/, 'table'], [/mushroom|toadstool/, 'mushroom'], [/statue|sculpture|monument|totem/, 'statue'],
  [/easel|paint|\bart\b|canvas|drawing/, 'easel'], [/bush|shrub|hedge|fern|berry/, 'bush'], [/mailbox|letterbox/, 'mailbox'], [/flag|banner/, 'flag'],
  [/boat|raft|canoe|ship/, 'boat'], [/snowman/, 'snowman'], [/telescope|observatory/, 'telescope'], [/piano|music|instrument|keyboard/, 'piano'],
  [/bee|hive|honey/, 'beehive'], [/path|trail|stepping|road/, 'path'], [/\bsign|signpost|noticeboard/, 'sign'],
];
function pickKind(it) {
  if (it.kind && B[it.kind]) return it.kind;
  const n = (it.name || '').toLowerCase();
  for (const [re, k] of KEYWORDS) if (re.test(n)) return k;
  return null;
}
export function textSprite(text, size = 96, color = '#000') {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'); x.font = `${size}px serif`; x.fillStyle = color; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(text, 64, 70);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false }));
}
const NO_SPIN = new Set(['pond', 'fountain', 'well', 'path']);
export function buildItem(it) {
  const g = new THREE.Group();
  const kind = pickKind(it), r = rng(it.id * 7 + 3);
  const o = { name: (it.name || '').toLowerCase(), color: /^#[0-9a-f]{6}$/i.test(it.color || '') ? it.color : null };
  if (kind) B[kind](g, o, r);
  else { // something new he invented: its emoji floating over a little plinth
    part(g, 'disc', '#d9cdb8', [0.9, 0.12, 0.9], [0, 0.06, 0]); part(g, 'disc', '#c4b79f', [1.1, 0.06, 1.1], [0, 0.03, 0]);
    const s = textSprite(it.emoji || '📦'); s.scale.set(1.5, 1.5, 1); s.position.y = 1.05; s.userData.bob = true; g.add(s);
  }
  if (!NO_SPIN.has(kind)) g.rotation.y = (Math.floor(r() * 5) - 2) * 0.22;
  g.traverse(n => { n.userData.item = it; });
  g.userData.kind = kind;
  return g;
}

// ---------------------------------------------------------------- Gino himself
export function buildGino() {
  const g = new THREE.Group(), fur = '#9c6b3a', dark = '#6b4628', light_ = '#b88a58';
  const fuzz = m => { if (m.userData.fuzz) return m; m.userData.fuzz = true; m.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace('#include <opaque_fragment>', 'float rimF = pow(1.0 - clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0), 2.2);\n outgoingLight += rimF * diffuseColor.rgb * 0.5 + rimF * vec3(0.06, 0.04, 0.02);\n#include <opaque_fragment>'); }; m.customProgramCacheKey = () => 'fuzz'; return m; };
  const F = c => fuzz(texMat('fur', c, furTex(), { bumpScale: 1.4, roughness: 1 }));
  const sm = { flatShading: false, roughness: 0.6 };
  const body = new THREE.Group(); g.add(body);
  // barrel body: high round rump, slightly lower shoulders, flatter belly, paler underneath
  const torsoG = sculpt(n => { const x = n.x, y = n.y, z = n.z, r = 1 - 0.13 * Math.max(0, x) ** 2;
    n.set(sq(x, 0.82) * 1.0, y * 0.52 * r * (y < 0 ? 1.0 : 1) + 0.09 * Math.max(0, -x) * Math.max(0, y), sq(z, 0.88) * 0.56 * r);
    return y < -0.25 ? 1.18 : 0.98 - 0.12 * y; });
  const torso = furShells(meshOf(body, torsoG, F(shade(fur, -0.06)), [1, 1, 1], [-0.08, 0.8, 0]), fur, 0.075);
  furShells(meshOf(body, geos.smooth, F(shade(fur, -0.06)), [0.72, 0.7, 0.74], [0.52, 0.88, 0]), fur, 0.06);                                // thick neck
  const head = new THREE.Group(); head.position.set(0.7, 1.02, 0); body.add(head);
  // big blocky capybara head: long deep muzzle with a blunt squared end
  const headG = sculpt(n => { const x = n.x, y = n.y, z = n.z, f = Math.max(0, x);
    n.set(x > 0 ? sq(x, 0.72) * 0.66 : x * 0.42, sq(y, 0.82) * 0.31 * (1 - 0.14 * f) - 0.05 * f + 0.02, sq(z, 0.85) * 0.3 * (1 - 0.24 * f * f));
    return 1 - 0.22 * Math.max(0, (x - 0.55) / 0.45) + (y < -0.3 ? 0.14 : 0); }, 40, 28);
  furShells(meshOf(head, headG, F(shade(fur, -0.05)), [1, 1, 1], [0.06, 0, 0]), fur, 0.03, 10);
  part(head, 'smooth', '#3a281a', [0.09, 0.12, 0.2], [0.715, 0.09, 0], null, { flatShading: false, roughness: 0.35 });                        // nose pad
  for (const s of [-1, 1]) part(head, 'smooth', '#1c120b', [0.035, 0.04, 0.05], [0.752, 0.105, s * 0.055], null, sm);
  part(head, 'box', '#2a1b10', [0.02, 0.07, 0.015], [0.752, 0.0, 0]); for (const s of [-1, 1]) part(head, 'box', '#2a1b10', [0.02, 0.016, 0.1], [0.745, -0.035, s * 0.045], [-s * 0.3, 0, 0]);                                  // mouth line
  for (const s of [-1, 1]) for (let i = 0; i < 3; i++) part(head, 'smooth', '#2a1b10', [0.016, 0.016, 0.016], [0.6 - i * 0.05, 0.0 - i * 0.025, s * 0.2], null, sm);   // whisker dots
  const ears = [], eyes = [];
  for (const s of [-1, 1]) {
    const ear = new THREE.Group(); ear.position.set(-0.17, 0.3, s * 0.21); head.add(ear);
    meshOf(ear, geos.smooth, F(dark), [0.15, 0.17, 0.08], [0, 0, 0], [s * 0.35, 0, 0]); part(ear, 'smooth', '#3a2416', [0.09, 0.11, 0.04], [0.02, 0, s * 0.03], [s * 0.35, 0, 0], sm);
    part(head, 'smooth', '#3a2416', [0.13, 0.13, 0.03], [0.2, 0.14, s * 0.268], null, sm);                  // dark skin round the eye
    ears.push(ear);
    eyes.push(part(head, 'smooth', '#140d08', [0.1, 0.105, 0.07], [0.2, 0.14, s * 0.272], null, { flatShading: false, roughness: 0.08 }));
    part(head, 'smooth', '#ffffff', [0.026, 0.026, 0.016], [0.224, 0.166, s * 0.305], null, { flatShading: false, emissive: '#ffffff', emissiveIntensity: 0.4 });
  }
  const orange = new THREE.Group(); orange.position.set(0, 0.36, 0); orange.visible = false; head.add(orange);
  part(orange, 'smooth', '#f6a623', [0.26, 0.24, 0.26], [0, 0.08, 0], null, { flatShading: false, roughness: 0.5 }); part(orange, 'sphere', '#4f9446', [0.12, 0.03, 0.07], [0.03, 0.21, 0]);
  const legs = [];
  for (const [x, z, back] of [[0.42, 0.27, 0], [0.42, -0.27, 0], [-0.5, 0.29, 1], [-0.5, -0.29, 1]]) {
    const pivot = new THREE.Group(); pivot.position.set(x, 0.46, z); body.add(pivot);
    furShells(meshOf(pivot, geos.smooth, F(shade(fur, -0.06)), back ? [0.46, 0.56, 0.3] : [0.32, 0.46, 0.27], [back ? -0.02 : 0, 0.02, 0]), fur, 0.05, 10);     // haunch / shoulder
    furShells(meshOf(pivot, geos.cyl, F(shade(fur, -0.12)), [0.2, 0.34, 0.2], [0.01, -0.24, 0]), shade(fur, -0.06), 0.022, 8);
    part(pivot, 'smooth', '#4a321d', [0.27, 0.11, 0.23], [0.05, -0.41, 0], null, sm);
    for (const t of [-1, 0, 1]) part(pivot, 'smooth', '#2e1e12', [0.07, 0.055, 0.06], [0.17, -0.43, t * 0.07], null, sm);  // toes
    legs.push(pivot);
  }
  const zs = [];
  for (let i = 0; i < 3; i++) { const s = textSprite('z', 80, '#dfe6ff'); s.visible = false; g.add(s); zs.push(s); }
  const hearts = [];
  for (let i = 0; i < 6; i++) { const s = textSprite('❤️', 80, '#e0445c'); s.visible = false; g.add(s); hearts.push(s); }
  const emote = textSprite('', 84); emote.scale.setScalar(0.62); emote.position.y = 2.15; g.add(emote);
  g.traverse(n => { n.userData.isGino = true; });
  g.userData = { body, head, legs, ears, eyes, zs, hearts, emote, orange, isGino: true };
  return g;
}
