// Gino's world through the year: decorations for each season and a little outfit for Gino.
// world.js asks for a "look" (christmas, winter, spring, sakura, summer, autumn) from the server's calendar, places
// the decorations on free spots of his meadow (never on top of his own things) and dresses the sculpted Gino.
import * as THREE from 'three';
import { buildItem } from './kit.js?v=2';

export const LOOKS = ['christmas', 'winter', 'spring', 'sakura', 'summer', 'autumn'];
const M = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.6, ...o });
const glowM = (c, k = 1.6) => new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: k, roughness: 0.3 });
const mesh = (geo, m, p = [0, 0, 0], s = 1) => { const o = new THREE.Mesh(geo, m); o.position.set(...p); typeof s === 'number' ? o.scale.setScalar(s) : o.scale.set(...s); o.castShadow = true; o.receiveShadow = true; return o; };
let r = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(7);
let groundY = () => 0;
const tickers = [];   // things that move every frame: twinkling bulbs, bobbing ducks, a spinning star

// a cosy Christmas tree: Gino's fir with baubles, warm lights, a star and presents
function christmasTree(at, size = 1.25) {
  const g = buildItem({ id: 77, kind: 'pine', name: 'christmas tree' }); g.rotation.y = 0;
  const cols = ['#d62f2f', '#f2c14e', '#2f6fd6', '#e8e8f0', '#c23ab0'];
  for (let i = 0; i < 46; i++) { const t = 0.04 + r() * 0.86, a = r() * 6.283, rad = 1.45 * (1 - t * 0.88) + 0.12, y = 1.3 + t * 4.7;
    g.add(mesh(new THREE.SphereGeometry(0.13, 14, 10), M(cols[i % 5], { metalness: 0.6, roughness: 0.2, emissive: cols[i % 5], emissiveIntensity: 0.15 }), [Math.cos(a) * rad, y, Math.sin(a) * rad])); }
  const bulbs = [];
  for (let i = 0; i < 120; i++) { const t = i / 120, a = t * 6.283 * 6.5, rad = 1.45 * (1 - t * 0.9) + 0.1, y = 1.25 + t * 4.8;
    const b = mesh(new THREE.SphereGeometry(0.055, 8, 6), glowM(['#ffd27a', '#ff6b5e', '#7fd0ff', '#9dff8a'][i % 4], 2.2), [Math.cos(a) * rad, y, Math.sin(a) * rad]); b.castShadow = false; g.add(b); bulbs.push(b); }
  tickers.push(t => bulbs.forEach((b, i) => { b.material.emissiveIntensity = 1.4 + Math.sin(t * 3 + i * 1.7) * 0.9; }));
  // star
  const sh = new THREE.Shape(); for (let i = 0; i < 10; i++) { const a = i / 10 * 6.283 + Math.PI / 2, rr = i % 2 ? 0.17 : 0.42; sh[i ? 'lineTo' : 'moveTo'](Math.cos(a) * rr, Math.sin(a) * rr); }
  const star = mesh(new THREE.ExtrudeGeometry(sh, { depth: 0.1, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.03, bevelSegments: 1 }), glowM('#ffd447', 1.8), [0, 6.45, -0.05]);
  g.add(star); tickers.push(t => { star.rotation.y = Math.sin(t * 0.7) * 0.5; });
  g.position.copy(at); g.scale.setScalar(size); return g;
}
function present(c, ribbon, s) {
  const g = new THREE.Group();
  g.add(mesh(new THREE.BoxGeometry(1, 1, 1), M(c, { roughness: 0.45 }), [0, 0.5, 0]));
  g.add(mesh(new THREE.BoxGeometry(1.02, 1.02, 0.16), M(ribbon, { roughness: 0.3, metalness: 0.3 }), [0, 0.5, 0]));
  g.add(mesh(new THREE.BoxGeometry(0.16, 1.02, 1.02), M(ribbon, { roughness: 0.3, metalness: 0.3 }), [0, 0.5, 0]));
  for (const s2 of [-1, 1]) { const bow = mesh(new THREE.TorusGeometry(0.16, 0.05, 8, 16), M(ribbon, { metalness: 0.3, roughness: 0.3 }), [s2 * 0.13, 1.08, 0]); bow.rotation.set(0, s2 * 0.6, s2 * 0.7); g.add(bow); }
  g.scale.set(s[0], s[1], s[2]); return g;
}
function candyCane(h = 1.2) {
  const c = document.createElement('canvas'); c.width = 64; c.height = 256; const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 64, 256);
  x.fillStyle = '#d42a2a'; for (let i = -4; i < 12; i++) { x.beginPath(); x.moveTo(0, i * 32); x.lineTo(64, i * 32 + 32); x.lineTo(64, i * 32 + 48); x.lineTo(0, i * 32 + 16); x.fill(); }
  const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace; tx.wrapS = tx.wrapT = THREE.RepeatWrapping; tx.repeat.set(1, 3);
  const path = new THREE.CurvePath(); path.add(new THREE.LineCurve3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, h, 0)));
  path.add(new THREE.CubicBezierCurve3(new THREE.Vector3(0, h, 0), new THREE.Vector3(0, h + 0.35, 0), new THREE.Vector3(0.45, h + 0.35, 0), new THREE.Vector3(0.45, h, 0)));
  return mesh(new THREE.TubeGeometry(path, 40, 0.07, 10), new THREE.MeshStandardMaterial({ map: tx, roughness: 0.3 }));
}
// string of fairy lights hanging between two points
function lightString(a, b, sag = 0.6, n = 18, cols = ['#ffd27a', '#ff6b5e', '#7fd0ff', '#9dff8a']) {
  const g = new THREE.Group(), pts = [];
  for (let i = 0; i <= 40; i++) { const t = i / 40; pts.push(new THREE.Vector3().lerpVectors(a, b, t).add(new THREE.Vector3(0, -Math.sin(t * Math.PI) * sag, 0))); }
  const curve = new THREE.CatmullRomCurve3(pts); g.add(mesh(new THREE.TubeGeometry(curve, 40, 0.012, 4), M('#1d2a1d')));
  const bulbs = [];
  for (let i = 1; i < n; i++) { const p = curve.getPoint(i / n); const b = mesh(new THREE.SphereGeometry(0.06, 8, 6), glowM(cols[i % cols.length], 2), [p.x, p.y - 0.05, p.z]); b.castShadow = false; g.add(b); bulbs.push(b); }
  tickers.push(t => bulbs.forEach((b, i) => { b.material.emissiveIntensity = 1.5 + Math.sin(t * 2.5 + i * 2.1) * 0.8; }));
  return g;
}

// ---- Gino's outfits (stuck to his head and neck bones, so they move with him)
function bone(G, n) { return G.real && G.real.getObjectByName(n); }
function wear(G, obj, bodyPos, boneName = 'head') { obj.position.set(...bodyPos); G.body.add(obj); G.body.updateMatrixWorld(true); const b = bone(G, boneName) || G.head; b.attach(obj); }
function santaHat(G) {
  const g = new THREE.Group();
  const red = M('#c8202a', { roughness: 0.85 }), white = M('#fbfbf7', { roughness: 1 });
  // floppy cone: a bent tube that narrows to the tip
  const pts = []; for (let i = 0; i <= 12; i++) { const t = i / 12; pts.push(new THREE.Vector3(-Math.pow(t, 2.2) * 0.32, t * 0.42 - Math.pow(t, 3) * 0.12, 0)); }
  const curve = new THREE.CatmullRomCurve3(pts);
  const geo = new THREE.TubeGeometry(curve, 24, 1, 16, false); const p = geo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) { const seg = Math.floor(i / 17) / 24, c = curve.getPoint(seg); v.fromBufferAttribute(p, i).sub(c); const rad = 0.215 * (1 - seg) + 0.012; v.normalize().multiplyScalar(rad).add(c); p.setXYZ(i, v.x, v.y, v.z); }
  geo.computeVertexNormals(); g.add(mesh(geo, red));
  const brim = mesh(new THREE.TorusGeometry(0.21, 0.07, 12, 28), white, [0, 0.01, 0]); brim.rotation.x = Math.PI / 2; g.add(brim);
  const tip = curve.getPoint(1); g.add(mesh(new THREE.IcosahedronGeometry(0.075, 2), white, [tip.x, tip.y - 0.02, tip.z]));
  g.rotation.set(0, 0, -0.2); wear(G, g, [0.82, 1.46, 0]); return g;
}
function scarf(G, a = '#c8202a', b = '#2f8f4e') {
  const c = document.createElement('canvas'); c.width = 256; c.height = 32; const x = c.getContext('2d');
  for (let i = 0; i < 8; i++) { x.fillStyle = i % 2 ? b : a; x.fillRect(i * 32, 0, 32, 32); } x.fillStyle = 'rgba(255,255,255,.18)'; for (let i = 0; i < 256; i += 4) x.fillRect(i, 0, 1, 32);
  const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace; tx.wrapS = THREE.RepeatWrapping; tx.repeat.set(3, 1);
  const m = new THREE.MeshStandardMaterial({ map: tx, roughness: 1 });
  const g = new THREE.Group();
  const ring = mesh(new THREE.TorusGeometry(0.41, 0.095, 12, 40), m); ring.scale.set(1.12, 1.08, 1.3); ring.rotation.y = Math.PI / 2; g.add(ring);
  const tail = mesh(new THREE.BoxGeometry(0.1, 0.42, 0.15), new THREE.MeshStandardMaterial({ map: tx, roughness: 1 }), [0.12, -0.32, 0.46]); tail.rotation.set(-0.12, 0, 0.35); g.add(tail);
  for (let i = 0; i < 5; i++) g.add(mesh(new THREE.BoxGeometry(0.02, 0.07, 0.02), M(i % 2 ? a : b), [0.2, -0.54, 0.4 + i * 0.03]));
  g.rotation.z = -0.5; wear(G, g, [0.55, 0.97, 0], 'neck'); return g;
}
function flowerCrown(G) {
  const g = new THREE.Group();
  const petalGeo = new THREE.SphereGeometry(0.05, 10, 6); petalGeo.scale(1, 0.35, 0.7);
  const pinks = ['#f9c6d8', '#f4a9c4', '#ffffff', '#fbd8e4'];
  for (let i = 0; i < 9; i++) { const a = i / 9 * 6.283, f = new THREE.Group(); f.position.set(Math.cos(a) * 0.25, Math.sin(a * 2) * 0.015, Math.sin(a) * 0.31); f.scale.setScalar(1.9);
    for (let k = 0; k < 5; k++) { const pa = k / 5 * 6.283, pt = mesh(petalGeo, M(pinks[i % 4], { roughness: 0.7 }), [Math.cos(pa) * 0.045, 0.02, Math.sin(pa) * 0.045]); pt.rotation.y = -pa; f.add(pt); }
    f.add(mesh(new THREE.SphereGeometry(0.022, 8, 6), M('#f2c14e'), [0, 0.03, 0])); f.rotation.set((r() - 0.5) * 0.6, 0, (r() - 0.5) * 0.6); g.add(f);
    const lf = mesh(new THREE.SphereGeometry(0.04, 8, 6), M('#6fae4f'), [Math.cos(a + 0.35) * 0.26, 0, Math.sin(a + 0.35) * 0.32], [1.8, 0.45, 0.9]); g.add(lf); }
  g.rotation.z = -0.3; g.scale.setScalar(0.8); wear(G, g, [0.9, 1.36, 0]); return g;
}

// ---- cherry blossom bits
function groundPetals(center, n = 2600, spread = 36) {
  const geo = new THREE.CircleGeometry(0.07, 6); geo.rotateX(-Math.PI / 2);
  const inst = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.9 }), n), o = new THREE.Object3D(), c = new THREE.Color();
  for (let i = 0; i < n; i++) { const a = r() * 6.283, d = Math.sqrt(r()) * spread / 2, x = center.x + Math.cos(a) * d, z = center.z + Math.sin(a) * d;
    o.position.set(x, groundY(x, z) + 0.06, z); o.rotation.set((r() - 0.5) * 0.4, r() * 6.28, 0); o.scale.set(1 + r() * 0.6, 1, 0.6 + r() * 0.4); o.updateMatrix(); inst.setMatrixAt(i, o.matrix);
    inst.setColorAt(i, c.set(['#ffd3e2', '#f9bcd2', '#ffffff', '#f4a9c4'][i % 4])); }
  inst.receiveShadow = true; return inst;
}
function lantern() {
  const g = new THREE.Group(); const geo = new THREE.SphereGeometry(0.26, 16, 12); geo.scale(1, 1.25, 1);
  const body = mesh(geo, new THREE.MeshStandardMaterial({ color: '#e8473b', emissive: '#ff8a4a', emissiveIntensity: 0.9, roughness: 0.8 })); g.add(body);
  for (const y of [-0.3, 0.3]) g.add(mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.06, 14), M('#1b1b1b'), [0, y, 0]));
  const band = mesh(new THREE.TorusGeometry(0.262, 0.012, 6, 24), M('#1b1b1b')); band.rotation.x = Math.PI / 2; g.add(band);
  g.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.25, 6), M('#e6c34a'), [0, -0.45, 0]));
  return g;
}
function torii() {
  const g = new THREE.Group(), red = M('#d23a22', { roughness: 0.55 }), blk = M('#222', { roughness: 0.7 });
  for (const s of [-1, 1]) { g.add(mesh(new THREE.CylinderGeometry(0.17, 0.2, 3.6, 14), red, [s * 1.5, 1.8, 0])); g.add(mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.35, 14), blk, [s * 1.5, 0.17, 0])); }
  g.add(mesh(new THREE.BoxGeometry(3.7, 0.22, 0.3), red, [0, 2.9, 0]));
  const top = mesh(new THREE.BoxGeometry(4.6, 0.28, 0.42), red, [0, 3.55, 0]); g.add(top);
  g.add(mesh(new THREE.BoxGeometry(4.9, 0.14, 0.5), blk, [0, 3.75, 0]));
  g.add(mesh(new THREE.BoxGeometry(0.22, 0.5, 0.25), red, [0, 3.2, 0]));
  return g;
}
function dango() { // three-colour sweet on a stick, Gino's hanami snack
  const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.5, 5), M('#d8b98a'), [0, 0.25, 0]));
  ['#f6a9c0', '#fdfbf2', '#8fc46a'].forEach((c, i) => g.add(mesh(new THREE.SphereGeometry(0.06, 12, 8), M(c, { roughness: 0.5 }), [0, 0.16 + i * 0.11, 0]))); return g;
}


// ---- spring / summer / autumn bits
function bunnyEars(G) {
  const g = new THREE.Group(), white = M('#fbf8f3', { roughness: 0.9 }), pink = M('#f6b3c8', { roughness: 0.8 });
  const band = mesh(new THREE.TorusGeometry(0.3, 0.028, 8, 32, Math.PI), M('#f27ca0')); band.scale.set(1.3, 1, 1); band.rotation.y = Math.PI / 2; g.add(band);
  for (const s2 of [-1, 1]) { const e = new THREE.Group(); e.position.set(0, 0.26, s2 * 0.13); e.rotation.x = s2 * -0.22;
    const outer = new THREE.SphereGeometry(0.09, 16, 12); outer.scale(0.45, 2.3, 1); e.add(mesh(outer, white, [0, 0.19, 0]));
    const inner = new THREE.SphereGeometry(0.06, 14, 10); inner.scale(0.3, 2.3, 1); e.add(mesh(inner, pink, [0.03, 0.17, 0])); if (s2 > 0) e.rotation.z = -0.35; g.add(e); }
  g.rotation.z = -0.15; wear(G, g, [0.8, 1.15, 0]); return g;
}
function egg(c1, c2) { const geo = new THREE.SphereGeometry(0.16, 16, 12); geo.scale(1, 1.3, 1);
  const c = document.createElement('canvas'); c.width = 64; c.height = 64; const x = c.getContext('2d'); x.fillStyle = c1; x.fillRect(0, 0, 64, 64); x.fillStyle = c2;
  for (let i = 0; i < 3; i++) x.fillRect(0, 12 + i * 18, 64, 6); x.fillStyle = '#fff'; for (let i = 0; i < 8; i++) { x.beginPath(); x.arc(4 + i * 8, 21 + (i % 2) * 18, 2.4, 0, 6.3); x.fill(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; const m = mesh(geo, new THREE.MeshStandardMaterial({ map: t, roughness: 0.45 })); return m; }
function rainbow(at) {
  const g = new THREE.Group(), cols = ['#ff5a5a', '#ff9e3d', '#ffe14d', '#6fd36a', '#4ab3ff', '#8a6cf0'];
  cols.forEach((c, i) => { const m = new THREE.Mesh(new THREE.TorusGeometry(46 - i * 1.6, 0.8, 8, 80, Math.PI), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.55, fog: false, depthWrite: false })); g.add(m); });
  g.position.copy(at); return g;
}
function duck(s = 1) { const g = new THREE.Group(), y = M('#ffd84a', { roughness: 0.7 });
  const b = new THREE.SphereGeometry(0.2, 14, 10); b.scale(1.3, 0.8, 1); g.add(mesh(b, y, [0, 0.12, 0]));
  g.add(mesh(new THREE.SphereGeometry(0.12, 12, 10), y, [0.2, 0.32, 0]));
  const bk = new THREE.ConeGeometry(0.04, 0.1, 8); bk.rotateZ(-Math.PI / 2); g.add(mesh(bk, M('#f28a2c'), [0.33, 0.31, 0]));
  for (const s2 of [-1, 1]) g.add(mesh(new THREE.SphereGeometry(0.018, 6, 6), M('#111'), [0.28, 0.36, s2 * 0.07]));
  g.scale.setScalar(s); return g; }
function sunHat(G) { const g = new THREE.Group(), straw = M('#e8c779', { roughness: 0.95 });
  g.add(mesh(new THREE.CylinderGeometry(0.34, 0.35, 0.025, 32), straw, [0, 0.03, 0]));
  g.add(mesh(new THREE.CylinderGeometry(0.17, 0.25, 0.22, 24), straw, [0, 0.12, 0]));
  g.add(mesh(new THREE.CylinderGeometry(0.245, 0.25, 0.06, 24), M('#e0435a'), [0, 0.07, 0]));
  g.add(mesh(new THREE.SphereGeometry(0.05, 10, 8), M('#ffffff'), [0, 0.09, 0.25])); g.add(mesh(new THREE.SphereGeometry(0.025, 8, 6), M('#f6c833'), [0, 0.1, 0.29]));
  g.rotation.z = -0.08; wear(G, g, [0.78, 1.36, 0]); return g; }
function lei(G) { const g = new THREE.Group(), cols = ['#ff5a7a', '#ffe14d', '#ffffff', '#ff9e3d', '#c86cf0'];
  const pg = new THREE.SphereGeometry(0.055, 10, 6); pg.scale(1, 0.5, 1);
  for (let i = 0; i < 34; i++) { const a = i / 34 * 6.283, f = new THREE.Group(); f.position.set(0, Math.cos(a) * 0.44, Math.sin(a) * 0.5);
    for (let k = 0; k < 5; k++) { const pa = k / 5 * 6.283; f.add(mesh(pg, M(cols[i % 5], { roughness: 0.7 }), [Math.cos(pa) * 0.05, 0, Math.sin(pa) * 0.05])); }
    f.add(mesh(new THREE.SphereGeometry(0.025, 6, 4), M('#f2c14e'), [0, 0.02, 0])); f.rotation.set(a, 0, Math.PI / 2); g.add(f); }
  g.rotation.z = -0.5; wear(G, g, [0.55, 0.95, 0], 'neck'); return g; }
function umbrella() { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.6, 8), M('#f3efe6'), [0, 1.3, 0]));
  const c = document.createElement('canvas'); c.width = 256; c.height = 32; const x = c.getContext('2d'); for (let i = 0; i < 8; i++) { x.fillStyle = i % 2 ? '#ffffff' : '#e0435a'; x.fillRect(i * 32, 0, 32, 32); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  const top = mesh(new THREE.ConeGeometry(1.6, 0.6, 8, 1, true), new THREE.MeshStandardMaterial({ map: t, side: THREE.DoubleSide, roughness: 0.8 }), [0, 2.55, 0]); g.add(top);
  g.add(mesh(new THREE.SphereGeometry(0.07, 8, 6), M('#e0435a'), [0, 2.88, 0])); g.rotation.z = 0.12; return g; }
function towel(c1, c2) { const c = document.createElement('canvas'); c.width = 64; c.height = 128; const x = c.getContext('2d'); for (let i = 0; i < 8; i++) { x.fillStyle = i % 2 ? c2 : c1; x.fillRect(0, i * 16, 64, 16); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; const m = mesh(new THREE.BoxGeometry(0.9, 0.03, 1.8), new THREE.MeshStandardMaterial({ map: t, roughness: 1 })); return m; }
function watermelon() { const g = new THREE.Group();
  const geo = new THREE.CylinderGeometry(0.4, 0.4, 0.12, 24, 1, false, 0, Math.PI); geo.rotateX(Math.PI / 2);
  const red = mesh(geo, M('#f0465a', { roughness: 0.6 })); red.scale.set(1, 1, 1); g.add(red);
  const rind = mesh(new THREE.TorusGeometry(0.4, 0.04, 6, 24, Math.PI), M('#3f8f3a')); g.add(rind);
  for (let i = 0; i < 7; i++) { const a = 0.3 + i * 0.37; g.add(mesh(new THREE.SphereGeometry(0.018, 6, 4), M('#111'), [Math.cos(a) * 0.24, Math.sin(a) * 0.24, 0.062])); }
  return g; }
function swimRing() { const c = document.createElement('canvas'); c.width = 256; c.height = 16; const x = c.getContext('2d'); for (let i = 0; i < 8; i++) { x.fillStyle = i % 2 ? '#ffffff' : '#ff7a3d'; x.fillRect(i * 32, 0, 32, 16); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; const m = mesh(new THREE.TorusGeometry(0.5, 0.18, 14, 32), new THREE.MeshStandardMaterial({ map: t, roughness: 0.3 })); m.rotation.x = Math.PI / 2; return m; }
function beanie(G, main = '#d8762e', cuffC = '#9a4a1f') { const g = new THREE.Group();
  const c = document.createElement('canvas'); c.width = 64; c.height = 64; const x = c.getContext('2d'); x.fillStyle = main; x.fillRect(0, 0, 64, 64); x.fillStyle = 'rgba(0,0,0,.15)'; for (let i = 0; i < 64; i += 4) x.fillRect(i, 0, 2, 64);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = THREE.RepeatWrapping; t.repeat.set(6, 1);
  const dome = new THREE.SphereGeometry(0.26, 24, 14, 0, Math.PI * 2, 0, Math.PI / 2); dome.scale(1, 0.95, 1.15); g.add(mesh(dome, new THREE.MeshStandardMaterial({ map: t, roughness: 1 }), [0, 0.03, 0]));
  const cuff = mesh(new THREE.TorusGeometry(0.265, 0.06, 10, 32), M(cuffC, { roughness: 1 })); cuff.rotation.x = Math.PI / 2; cuff.scale.set(1, 1.15, 1); g.add(cuff);
  g.add(mesh(new THREE.IcosahedronGeometry(0.09, 2), M('#f2e3c6', { roughness: 1 }), [0, 0.3, 0]));
  g.rotation.z = -0.22; wear(G, g, [0.82, 1.4, 0]); return g; }
function leafPile(n = 160, rad = 0.9) { const g = new THREE.Group(); const geo = new THREE.CircleGeometry(0.09, 5); const cols = ['#e08a2e', '#d4552f', '#e6b93a', '#b9502a'];
  const inst = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ side: THREE.DoubleSide, roughness: 0.9 }), n), o = new THREE.Object3D(), c = new THREE.Color();
  for (let i = 0; i < n; i++) { const a = r() * 6.28, d = Math.sqrt(r()) * rad, h = (1 - d / rad) * 0.45 * r(); o.position.set(Math.cos(a) * d, h + 0.03, Math.sin(a) * d); o.rotation.set(r() * 6, r() * 6, r() * 6); o.scale.setScalar(0.8 + r() * 0.8); o.updateMatrix(); inst.setMatrixAt(i, o.matrix); inst.setColorAt(i, c.set(cols[i % 4])); }
  inst.castShadow = true; g.add(inst); return g; }
function jackOLantern(s = 1) { const g = new THREE.Group(); const geo = new THREE.SphereGeometry(0.4, 18, 12); geo.scale(1.15, 0.85, 1.15);
  const p = geo.attributes.position, v = new THREE.Vector3(); for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); const a = Math.atan2(v.z, v.x); const k = 1 - 0.06 * Math.pow(Math.abs(Math.cos(a * 4)), 3); p.setXYZ(i, v.x * k, v.y, v.z * k); } geo.computeVertexNormals();
  g.add(mesh(geo, M('#e8771f', { roughness: 0.6 }), [0, 0.34, 0]));
  g.add(mesh(new THREE.CylinderGeometry(0.04, 0.06, 0.16, 6), M('#5b7a2a'), [0, 0.74, 0]));
  const glow = glowM('#ffcf4a', 2.4);
  for (const s2 of [-1, 1]) { const e = new THREE.Shape(); e.moveTo(-0.07, 0); e.lineTo(0.07, 0); e.lineTo(0, 0.1); e.lineTo(-0.07, 0); const m = mesh(new THREE.ShapeGeometry(e), glow, [0.41, 0.42, s2 * 0.13]); m.rotation.y = Math.PI / 2; g.add(m); }
  const mouth = new THREE.Shape(); mouth.moveTo(-0.18, 0); mouth.quadraticCurveTo(0, -0.14, 0.18, 0); mouth.lineTo(0.1, -0.02); mouth.lineTo(0.06, 0.03); mouth.lineTo(0.0, -0.03); mouth.lineTo(-0.06, 0.03); mouth.lineTo(-0.1, -0.02); mouth.lineTo(-0.18, 0);
  const mm = mesh(new THREE.ShapeGeometry(mouth), glow, [0.42, 0.3, 0]); mm.rotation.y = Math.PI / 2; g.add(mm);
  g.scale.setScalar(s); return g; }
function hayBale() { const g = new THREE.Group(); const m = mesh(new THREE.BoxGeometry(1.1, 0.55, 0.65), M('#d9b45a', { roughness: 1 }), [0, 0.28, 0]); g.add(m);
  for (const z of [-0.18, 0.18]) g.add(mesh(new THREE.BoxGeometry(1.12, 0.57, 0.03), M('#8a5a2a'), [0, 0.28, z])); return g; }
function appleBasket() { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.35, 0.28, 0.3, 16, 1, true), M('#a9773e', { side: THREE.DoubleSide, roughness: 1 }), [0, 0.15, 0]));
  g.add(mesh(new THREE.CircleGeometry(0.28, 16), M('#7a5428'), [0, 0.02, 0])).children; for (let i = 0; i < 9; i++) { const a = i * 2.4, d = i ? 0.17 : 0; g.add(mesh(new THREE.SphereGeometry(0.09, 12, 8), M(i % 3 ? '#d9463e' : '#9ac43a', { roughness: 0.4 }), [Math.cos(a) * d, 0.3 + (i ? 0 : 0.05), Math.sin(a) * d])); }
  const h = mesh(new THREE.TorusGeometry(0.33, 0.025, 6, 20, Math.PI), M('#a9773e')); h.position.y = 0.3; g.add(h); return g; }


// ---------------------------------------------------------------- putting it all in his world
// Each piece asks for one free spot. Spots are picked near the middle of the things Gino has built, at least a
// cell and a bit away from any of them, so nothing ends up inside his house or on his bed.
function pieces(look, lite) {
  const P = [];
  const add = (make, opts = {}) => P.push({ make, ...opts });
  if (look === 'christmas') {
    add(() => christmasTree(new THREE.Vector3(), 1.25), { room: 1.6 });
    add(() => { const g = new THREE.Group(); [['#c8202a', '#f2c14e', [0.7, 0.55, 0.7], [0, 0]], ['#2f6fd6', '#f5f5f5', [0.55, 0.7, 0.55], [0.9, 0.5]], ['#2f8f4e', '#d62f2f', [0.9, 0.45, 0.6], [-0.4, 0.9]], ['#9b3fb8', '#f2c14e', [0.5, 0.5, 0.5], [0.6, -0.6]]]
      .forEach(([c, rb, s, [dx, dz]], i) => { const p = present(c, rb, s); p.position.set(dx, 0, dz); p.rotation.y = i * 0.7; g.add(p); }); return g; }, { near: 0 });
    add(() => buildItem({ id: 9001, kind: 'snowman', name: 'snowman', color: '#2f8f4e' }));
    add(() => { const g = new THREE.Group(), a = candyCane(1.3), b = candyCane(1.3); a.position.set(-1.4, 0, 0); b.position.set(1.4, 0, 0); b.rotation.y = Math.PI; g.add(a, b);
      g.add(lightString(new THREE.Vector3(-1.4, 1.45, 0), new THREE.Vector3(1.4, 1.45, 0), 0.35, 11)); return g; }, { room: 1.6 });
  } else if (look === 'winter') {
    add(() => buildItem({ id: 9002, kind: 'snowman', name: 'snowman', color: '#3f6fd6' }));
    if (!lite) add(() => { const s = buildItem({ id: 9003, kind: 'snowman', name: 'snowman', color: '#d9534f' }); s.scale.setScalar(0.75); return s; });
  } else if (look === 'spring') {
    const cols = [['#f6b3c8', '#7ab8f5'], ['#ffe14d', '#f27ca0'], ['#a8e0a0', '#b78cf0'], ['#b9d8ff', '#f6c833'], ['#d9c2ff', '#6fd36a'], ['#ffc48a', '#4ab3ff']];
    add(() => { const g = new THREE.Group(), b = appleBasket(); b.children.forEach(c => { if (c.geometry?.type === 'SphereGeometry') c.visible = false; }); g.add(b);
      for (let i = 0; i < 5; i++) { const e = egg(...cols[i]); e.scale.setScalar(0.75); e.position.set((i - 2) * 0.1, 0.34, (i % 2) * 0.1 - 0.05); g.add(e); } return g; });
    for (let k = 0; k < (lite ? 2 : 4); k++) add(() => { const g = new THREE.Group(); for (let i = 0; i < 3; i++) { const e = egg(...cols[(k * 3 + i) % 6]); e.position.set((r() - 0.5) * 1.6, 0.17, (r() - 0.5) * 1.6); e.rotation.set((r() - 0.5) * 0.8, r() * 6, (r() - 0.5) * 0.8); g.add(e); } return g; }, { room: 0.9 });
    ['#f2603d', '#f6c833', '#f27ca0'].slice(0, lite ? 1 : 3).forEach((c, i) => add(() => buildItem({ id: 9010 + i, kind: 'flowers', name: 'tulips', color: c }), { room: 1 }));
  } else if (look === 'sakura') {
    add(() => torii(), { room: 1.6 });
    add(() => { const g = new THREE.Group(), red = M('#7a5230', { roughness: 0.9 });
      for (const x of [-1.9, 1.9]) g.add(mesh(new THREE.CylinderGeometry(0.06, 0.08, 3.2, 8), red, [x, 1.6, 0]));
      g.add(lightString(new THREE.Vector3(-1.9, 3.0, 0), new THREE.Vector3(1.9, 3.0, 0), 0.4, 0, ['#000']));
      for (let i = 1; i < 5; i++) { const t = i / 5, l = lantern(); l.position.set(-1.9 + t * 3.8, 3.0 - Math.sin(t * Math.PI) * 0.4 - 0.45, 0); g.add(l); } return g; }, { room: 2 });
    add(() => { const g = new THREE.Group(); for (let i = 0; i < 3; i++) { const d = dango(); d.position.set(i * 0.15, 0.03, 0); d.rotation.set(Math.PI / 2 - 0.05, 0, 0.3 + i * 0.4); g.add(d); } return g; }, { room: 0.6 });
  } else if (look === 'summer') {
    add(() => { const g = new THREE.Group(); g.add(umbrella()); const a = towel('#4ab3ff', '#ffffff'); a.position.set(0.6, 0.02, 0.3); a.rotation.y = 0.3; g.add(a);
      if (!lite) { const b = towel('#ffe14d', '#f27ca0'); b.position.set(-0.7, 0.02, 0.5); b.rotation.y = -0.2; g.add(b); } return g; }, { room: 1.5 });
    add(() => { const g = new THREE.Group(); for (let i = 0; i < 3; i++) { const w = watermelon(); w.position.set(i * 0.5, 0.06, (i % 2) * 0.4); w.rotation.set(-Math.PI / 2, 0, i * 0.8); g.add(w); } return g; });
    add(() => { const c = document.createElement('canvas'); c.width = 128; c.height = 64; const x = c.getContext('2d'); ['#e0435a', '#ffffff', '#4ab3ff', '#ffe14d', '#ffffff', '#6fd36a'].forEach((col, i) => { x.fillStyle = col; x.fillRect(i * 22, 0, 22, 64); });
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return mesh(new THREE.SphereGeometry(0.3, 18, 12), new THREE.MeshStandardMaterial({ map: t, roughness: 0.3 }), [0, 0.3, 0]); }, { room: 0.6 });
    ['#f6c833', '#f6c833'].slice(0, lite ? 1 : 2).forEach((c, i) => add(() => buildItem({ id: 9020 + i, kind: 'flowers', name: 'sunflower patch' }), { room: 1 }));
  } else if (look === 'autumn') {
    [1.1, 0.8, 0.9, 1].slice(0, lite ? 2 : 4).forEach(s => add(() => leafPile(Math.round((lite ? 90 : 170) * s), 0.9 * s), { room: s }));
    add(() => { const g = new THREE.Group(); [[0, 0, 1], [0.6, 0.4, 0.7], [-0.4, 0.6, 0.6]].forEach(([x, z, s], i) => { const j = jackOLantern(s); j.position.set(x, 0, z); j.rotation.y = -0.6 + i * 0.3; g.add(j); }); return g; });
    add(() => { const g = new THREE.Group(), a = hayBale(), b = hayBale(); b.position.y = 0.55; b.scale.setScalar(0.9); b.rotation.y = 0.3; g.add(a, b); return g; });
    add(() => appleBasket(), { room: 0.6 });
  }
  return P;
}

export function seasonDecor({ scene, gino, look, lite, ground, cellX, cellZ, GW, GH }) {
  groundY = ground;
  const group = new THREE.Group(); group.name = 'season'; scene.add(group);
  const list = pieces(look, lite), objs = list.map(p => { const o = p.make(); o.visible = false; group.add(o); return o; });
  const extra = [];   // things that go with his pond or the sky, not on a spot of their own
  let sig = '', worn = [];
  if (look === 'spring') {
    const f = new THREE.Vector3(-15, 0, 23).normalize(), rb = new THREE.Group(), cols = ['#ff5a5a', '#ff9e3d', '#ffe14d', '#6fd36a', '#4ab3ff', '#8a6cf0'];
    cols.forEach((c, i) => rb.add(new THREE.Mesh(new THREE.TorusGeometry(70 - i * 2.4, 1.2, 8, 80, Math.PI), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.45, fog: false, depthWrite: false }))));
    rb.position.copy(f).multiplyScalar(-150).setY(-30); rb.rotation.y = Math.atan2(f.x, f.z); group.add(rb); extra.push({ sky: rb });
  }
  if (look === 'sakura') group.add(groundPetals(new THREE.Vector3(0, 0, 0), lite ? 700 : 2200, 34));
  return {
    group,
    // put the pieces on free spots; only redone when his things move
    place(habitat, ponds = []) {
      const taken = habitat.map(h => [h.x, h.y, Math.max(1, h.size || 1)]);
      const s = taken.map(t => t.join(',')).join(';') + '|' + ponds.length;
      if (s === sig) return; sig = s;
      const cx = taken.length ? taken.reduce((a, t) => a + t[0], 0) / taken.length : (GW - 1) / 2, cy = taken.length ? taken.reduce((a, t) => a + t[1], 0) / taken.length : (GH - 1) / 2;
      const spots = [];
      for (let x = 0; x <= GW - 1; x += 0.5) for (let y = 0; y <= GH - 1; y += 0.5) spots.push([x, y, Math.hypot(x - cx, (y - cy) * 1.3) + ((x * 7 + y * 13) % 5) * 0.04]);
      spots.sort((a, b) => a[2] - b[2]);
      const used = [];
      list.forEach((p, i) => {
        const o = objs[i], room = p.room || 0.8;
        const free = ([x, y]) => taken.every(([tx, ty, ts]) => Math.hypot(x - tx, y - ty) >= 0.9 + room * 0.5 + (ts - 1) * 0.5) && used.every(([ux, uy, ur]) => Math.hypot(x - ux, y - uy) >= ur + room * 0.6);
        let spot = null;
        if (p.near !== undefined && used[p.near]) { const [ux, uy] = used[p.near]; spot = [ux + 0.9, uy + 0.6]; }
        else spot = spots.find(free);
        if (!spot) { o.visible = false; used.push([-99, -99, 0]); return; }
        used.push([spot[0], spot[1], room]);
        const x = cellX(spot[0]), z = cellZ(spot[1]);
        o.position.set(x, groundY(x, z), z); o.rotation.y = ((spot[0] * 3 + spot[1]) % 4) * 0.4 - 0.6; o.visible = true;
      });
      // ducklings and a swim ring like ponds
      extra.filter(e => e.pond).forEach(e => { group.remove(e.pond); }); for (let i = extra.length - 1; i >= 0; i--) if (extra[i].pond) extra.splice(i, 1);
      const pond = ponds[0];
      if (pond && (look === 'spring' || look === 'summer')) {
        const g = new THREE.Group();
        if (look === 'spring') [[0, 0, 1], [0.6, 0.3, 0.6], [0.95, 0.5, 0.6], [1.3, 0.25, 0.6]].forEach(([dx, dz, s2]) => { const d = duck(s2); d.position.set(dx - 0.5, 0, dz - 0.3); d.rotation.y = -0.4; g.add(d); });
        else { const ring = swimRing(); ring.position.set(0.4, 0, 0.3); g.add(ring); }
        g.position.set(pond.position.x, -0.08, pond.position.z); group.add(g); extra.push({ pond: g });
      }
    },
    // the outfit, on the sculpted Gino's head and neck (the old simple Gino keeps his own look)
    dress() {
      const G = gino.userData; if (!G.real || worn.length) return;
      worn = { christmas: () => [santaHat(G), scarf(G)], winter: () => [beanie(G, '#3f6fd6', '#1f3f8f'), scarf(G, '#3f6fd6', '#ffffff')], spring: () => [bunnyEars(G)],
        sakura: () => [flowerCrown(G)], summer: () => [sunHat(G), lei(G)], autumn: () => [beanie(G), scarf(G, '#b5542a', '#e6b93a')] }[look]?.() || [];
      worn.forEach(o => o.traverse(n => { n.userData.isGino = true; }));
    },
    tick(t, day) {
      tickers.forEach(f => f(t));
      const G = gino.userData; if (worn.length) worn[0].visible = !G.orange?.visible;   // the orange hat (pond spa) wins
      extra.forEach(e => { if (e.sky) e.sky.visible = day > 0.6; if (e.pond) e.pond.position.y = -0.1 + Math.sin(t * 1.6) * 0.02; });
    },
  };
}
