// Modelling kit for Gino's world: every object is built from simple shapes, no model files. three.js r186.
import * as THREE from 'three';

export const U = { time: { value: 0 } };           // shared shader clock
export const env = { season: 'summer', art: [], artKey: '' };

const mats = new Map();
export function mat(color, extra = {}) {
  const key = color + JSON.stringify(extra);
  if (!mats.has(key)) mats.set(key, new THREE.MeshStandardMaterial({ color, roughness: 0.9, flatShading: true, ...extra }));
  return mats.get(key);
}
export const geos = {
  box: new THREE.BoxGeometry(1, 1, 1),
  sphere: new THREE.IcosahedronGeometry(0.5, 1),
  smooth: new THREE.SphereGeometry(0.5, 24, 16),
  cyl: new THREE.CylinderGeometry(0.5, 0.5, 1, 10),
  cone: new THREE.ConeGeometry(0.5, 1, 8),
  pyramid: new THREE.ConeGeometry(0.5, 1, 4),
  disc: new THREE.CylinderGeometry(0.5, 0.5, 1, 28),
  torus: new THREE.TorusGeometry(0.5, 0.18, 8, 18),
  plane: new THREE.PlaneGeometry(1, 1),
};
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
const leafMat = c => { const k = 'leaf' + c; if (!mats.has(k)) mats.set(k, windy(new THREE.MeshStandardMaterial({ color: c, roughness: 0.9, flatShading: true }), 'sway', 0.035)); return mats.get(k); };

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

// ---------------------------------------------------------------- everything Gino can build
export const B = {
  tree(g, o, r) {
    part(g, 'cyl', '#7a5230', [0.35, 1.7, 0.35], [0, 0.85, 0]);
    part(g, 'cyl', '#7a5230', [0.14, 0.8, 0.14], [0.3, 1.5, 0], [0, 0, -0.8]);
    const c = () => leafMat(o.color || leaf(r));
    part(g, 'sphere', c(), [2.1, 1.8, 2.1], [0, 2.3, 0], [r(), r(), 0]);
    part(g, 'sphere', c(), [1.4, 1.3, 1.4], [0.7, 3.0, 0.2], [r(), r(), 0]);
    part(g, 'sphere', c(), [1.3, 1.1, 1.3], [-0.65, 2.8, -0.3], [r(), r(), 0]);
    part(g, 'sphere', c(), [1.0, 0.9, 1.0], [0.1, 3.5, -0.2], [r(), r(), 0]);
  },
  fruit_tree(g, o, r) {
    B.tree(g, { color: env.season === 'winter' ? null : '#4f9446' }, r);
    const fc = o.color || (/apple|cherry/.test(o.name) ? '#d9463e' : /lemon|banana/.test(o.name) ? '#f2d64b' : /plum|berry/.test(o.name) ? '#8a4fc9' : '#f39a2e');
    for (let i = 0; i < 11; i++) { const a = r() * 6.28, h = 1.8 + r() * 1.5; part(g, 'smooth', fc, [0.24, 0.24, 0.24], [Math.cos(a) * 1.0, h, Math.sin(a) * 1.0], null, { flatShading: false, roughness: 0.5 }); }
  },
  pine(g, o) {
    part(g, 'cyl', '#6e4a2c', [0.3, 1, 0.3], [0, 0.5, 0]);
    const c = leafMat(o.color || (env.season === 'winter' ? '#5f8f7a' : '#3f7d4e'));
    part(g, 'cone', c, [2.1, 1.6, 2.1], [0, 1.5, 0]); part(g, 'cone', c, [1.6, 1.4, 1.6], [0, 2.4, 0]); part(g, 'cone', c, [1.05, 1.3, 1.05], [0, 3.3, 0]);
    if (env.season === 'winter') for (const [s, y] of [[1.5, 2.05], [1.1, 2.9], [0.6, 3.75]]) part(g, 'cone', '#f4f8fa', [s, 0.5, s], [0, y, 0]);
  },
  bush(g, o, r) {
    const c = () => leafMat(o.color || leaf(r));
    part(g, 'sphere', c(), [1.1, 0.8, 1.0], [0, 0.35, 0]); part(g, 'sphere', c(), [0.8, 0.6, 0.8], [0.55, 0.3, 0.2]); part(g, 'sphere', c(), [0.7, 0.6, 0.7], [-0.5, 0.28, -0.2]);
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
    part(g, 'sphere', c, [1.3, 0.9, 1.1], [0, 0.35, 0], [r(), r(), r()]);
    part(g, 'sphere', c, [0.7, 0.5, 0.6], [0.7, 0.2, 0.3], [r(), r(), r()]);
    part(g, 'sphere', '#6f9a58', [0.6, 0.12, 0.5], [-0.1, 0.78, 0]);
  },
  pond(g, o, r) {
    const wm = new THREE.MeshStandardMaterial({ color: o.color || '#5fb4dc', transparent: true, opacity: 0.85, roughness: 0.08, metalness: 0.2 });
    const w = part(g, 'disc', wm, [3.6, 0.06, 3.0], [0, 0.05, 0]); w.castShadow = false; w.userData.water = true;
    part(g, 'disc', '#2f7ea8', [2.8, 0.05, 2.3], [0, 0.03, 0]).castShadow = false;
    part(g, 'disc', '#d9c9a0', [4.1, 0.04, 3.5], [0, 0.0, 0]).castShadow = false;
    for (let i = 0; i < 13; i++) { const a = i / 13 * 6.28 + r() * 0.3, s = 0.25 + r() * 0.35; part(g, 'sphere', '#9a968c', [s, s * 0.6, s], [Math.cos(a) * 1.85, 0.08, Math.sin(a) * 1.55], [r(), r(), 0]); }
    for (let i = 0; i < 4; i++) { const a = r() * 6.28, d = r() * 1.0, x = Math.cos(a) * d, z = Math.sin(a) * d; part(g, 'disc', '#6bbf59', [0.42, 0.03, 0.42], [x, 0.09, z]).castShadow = false; if (i < 2) part(g, 'sphere', '#f7b3cf', [0.16, 0.12, 0.16], [x, 0.14, z]); }
    for (let i = 0; i < 6; i++) { const a = r() * 6.28; const m = part(g, 'cyl', leafMat('#7fae52'), [0.05, 1.0, 0.05], [Math.cos(a) * 1.7, 0.5, Math.sin(a) * 1.4]); part(g, 'cyl', '#6b4423', [0.09, 0.25, 0.09], [m.position.x, 1.0, m.position.z]); }
  },
  fountain(g, o) {
    part(g, 'disc', '#bdb7ab', [2.2, 0.35, 2.2], [0, 0.17, 0]);
    const w = part(g, 'disc', '#6fc0e6', [1.9, 0.1, 1.9], [0, 0.32, 0], null, { transparent: true, opacity: 0.85, roughness: 0.1 }); w.castShadow = false;
    part(g, 'cyl', '#bdb7ab', [0.3, 1.0, 0.3], [0, 0.7, 0]); part(g, 'disc', '#cfc9bd', [0.8, 0.12, 0.8], [0, 1.2, 0]);
    emitter(g, 10, o.color || '#bfe6fb', [0, 1.3, 0], { rise: 0.9, spread: 0.7, size: 0.11, arc: true, speed: 0.6 });
  },
  well(g, o) {
    part(g, 'cyl', '#a9a399', [1.2, 0.7, 1.2], [0, 0.35, 0]); part(g, 'disc', '#2f6f95', [0.95, 0.05, 0.95], [0, 0.69, 0]);
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
    for (let i = 0; i < 7; i++) { const a = i / 6 * Math.PI; part(g, 'sphere', leafMat(leaf(r)), [0.4, 0.3, 0.45], [Math.cos(a) * 0.85, 1.85 + Math.sin(a) * 0.72, 0.1]); }
  },
  lamp(g, o) {
    part(g, 'cyl', '#3f3f47', [0.1, 1.9, 0.1], [0, 0.95, 0]); part(g, 'cyl', '#3f3f47', [0.3, 0.1, 0.3], [0, 0.05, 0]);
    part(g, 'pyramid', '#3f3f47', [0.55, 0.22, 0.55], [0, 2.22, 0], [0, Math.PI / 4, 0]);
    nightGlow(part(g, 'smooth', '#fff3cf', [0.34, 0.36, 0.34], [0, 1.95, 0]), o.color || '#ffcf66', 4);
    light(g, o.color || '#ffcf66', [0, 1.95, 0], 16);
  },
  campfire(g, o) {
    for (let i = 0; i < 8; i++) { const a = i / 8 * 6.28; part(g, 'sphere', '#8d8a84', [0.3, 0.22, 0.3], [Math.cos(a) * 0.62, 0.08, Math.sin(a) * 0.62]); }
    for (let i = 0; i < 3; i++) part(g, 'cyl', '#5a3a20', [0.13, 0.95, 0.13], [0, 0.22, 0], [1.1, i * 2.1, 0]);
    for (const [s, h, c, e] of [[0.55, 0.95, '#ff8a2c', '#ff5a00'], [0.32, 0.65, '#ffd24a', '#ffb000']]) { const f = part(g, 'cone', c, [s, h, s], [0, 0.3 + h / 2, 0], null, { emissive: e, emissiveIntensity: 2.6, transparent: true, opacity: 0.92 }); f.castShadow = false; f.userData.flame = h; }
    emitter(g, 6, '#ffb347', [0, 0.9, 0], { rise: 2.2, spread: 0.5, size: 0.06, emissive: '#ff8a00', glow: 3, speed: 0.5 });
    emitter(g, 4, '#8a8a8a', [0, 1.2, 0], { rise: 2.6, spread: 0.5, size: 0.4, speed: 0.16 });
    light(g, '#ff8a3c', [0, 0.9, 0], 18, true);
  },
  house(g, o) {
    part(g, 'box', o.color || '#e8d3b0', [2.1, 1.4, 1.8], [0, 0.7, 0]);
    part(g, 'pyramid', '#b5553c', [3.3, 1.2, 3.0], [0, 2.0, 0], [0, Math.PI / 4, 0]);
    part(g, 'box', '#8d8a84', [0.32, 0.9, 0.32], [0.6, 2.1, -0.3]);
    part(g, 'box', '#6b4a2f', [0.55, 0.9, 0.06], [0, 0.45, 0.91]); part(g, 'smooth', '#f6c833', [0.07, 0.07, 0.07], [0.18, 0.45, 0.95]);
    for (const p of [[0.68, 0.85, 0.91, 0], [-0.68, 0.85, 0.91, 0], [1.06, 0.85, 0, 1]]) { const w = nightGlow(part(g, 'box', '#a9d8ee', [0.42, 0.42, 0.05], [p[0], p[1], p[2]], [0, p[3] * Math.PI / 2, 0]), '#ffc76a', 2.6); w.castShadow = false; }
    emitter(g, 5, '#d8d8d8', [0.6, 2.6, -0.3], { rise: 2.4, spread: 0.45, size: 0.36, speed: 0.14 });
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
  const g = new THREE.Group(), fur = '#a9733c', dark = '#7a5230', light_ = '#c08d58';
  const sm = { flatShading: false, roughness: 0.95 };
  const body = new THREE.Group(); g.add(body);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.5, 0.8, 8, 18), mat(fur, sm));
  torso.rotation.z = Math.PI / 2; torso.position.set(-0.02, 0.76, 0); torso.scale.set(1, 1, 1.1); torso.castShadow = true; body.add(torso);
  part(body, 'smooth', fur, [0.95, 0.95, 1.05], [-0.42, 0.82, 0], null, sm);                     // round rump
  part(body, 'smooth', light_, [1.2, 0.5, 0.8], [0, 0.42, 0], null, sm);                        // paler belly
  const head = new THREE.Group(); head.position.set(0.7, 1.02, 0); body.add(head);
  part(head, 'smooth', fur, [0.74, 0.66, 0.66], [0.05, 0, 0], null, sm);
  const snout = new THREE.Mesh(new THREE.CapsuleGeometry(0.21, 0.22, 6, 14), mat(light_, sm));  // blunt capybara muzzle
  snout.rotation.z = Math.PI / 2; snout.position.set(0.42, -0.07, 0); snout.scale.set(1, 1, 1.15); snout.castShadow = true; head.add(snout);
  part(head, 'smooth', dark, [0.1, 0.2, 0.3], [0.66, -0.03, 0], null, sm);
  for (const s of [-1, 1]) part(head, 'smooth', '#3d2a18', [0.05, 0.06, 0.06], [0.7, 0.03, s * 0.08], null, sm);
  const ears = [], eyes = [];
  for (const s of [-1, 1]) {
    ears.push(part(head, 'smooth', dark, [0.17, 0.17, 0.1], [-0.14, 0.31, s * 0.21], null, sm));
    eyes.push(part(head, 'smooth', '#1a120c', [0.105, 0.105, 0.06], [0.22, 0.11, s * 0.28], null, { flatShading: false, roughness: 0.15 }));
    part(head, 'smooth', '#ffffff', [0.03, 0.03, 0.02], [0.245, 0.135, s * 0.305], null, { flatShading: false, emissive: '#ffffff', emissiveIntensity: 0.4 });
    part(head, 'smooth', '#e8a08a', [0.14, 0.09, 0.04], [0.3, -0.06, s * 0.275], null, { flatShading: false, transparent: true, opacity: 0.55 }); // blush
  }
  const orange = new THREE.Group(); orange.position.set(0, 0.36, 0); orange.visible = false; head.add(orange);      // the classic: a yuzu on his head in the bath
  part(orange, 'smooth', '#f6a623', [0.26, 0.24, 0.26], [0, 0.08, 0], null, { flatShading: false, roughness: 0.5 }); part(orange, 'sphere', '#4f9446', [0.12, 0.03, 0.07], [0.03, 0.21, 0]);
  const legs = [];
  for (const [x, z] of [[0.42, 0.27], [0.42, -0.27], [-0.45, 0.28], [-0.45, -0.28]]) {
    const pivot = new THREE.Group(); pivot.position.set(x, 0.46, z); body.add(pivot);
    part(pivot, 'cyl', dark, [0.2, 0.44, 0.2], [0, -0.2, 0], null, sm); part(pivot, 'smooth', '#5e3f24', [0.26, 0.12, 0.24], [0.04, -0.42, 0], null, sm);
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
