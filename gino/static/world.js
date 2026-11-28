// Gino's 3D world. three.js r186, WebGLRenderer + bloom. Everything is procedural (no model or texture files).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { FXAAPass } from 'three/addons/postprocessing/FXAAPass.js';
import { U, env, B, mat, geos, part, rng, windy, buildItem, buildGino, textSprite, waterMat as sharedWater, ripples } from './kit.js?v=2';   // ?v= makes phones that kept an old copy fetch the new one

const CELL = 2, GW = 16, GH = 10, WATER_Y = -0.3;
const LAKE = { x: 7, z: -29, r: 13 };
const cellX = x => (x - (GW - 1) / 2) * CELL;
const cellZ = y => (y - (GH - 1) / 2) * CELL;
const smooth = (a, b, v) => THREE.MathUtils.smoothstep(v, a, b);
const C = h => new THREE.Color(h);

// ---------------------------------------------------------------- land shape
function lakeK(x, z) { return 1 - smooth(LAKE.r * 0.72, LAKE.r, Math.hypot((x - LAKE.x) * 0.8, z - LAKE.z)); }
export function groundY(x, z) {
  const dx = Math.max(0, Math.abs(x) - GW), dz = Math.max(0, Math.abs(z) - GH);
  const e = smooth(0, 1, Math.min(1, Math.hypot(dx, dz) / 16));
  const far = smooth(40, 120, Math.hypot(x, z));
  const hills = Math.sin(x * 0.21) * Math.cos(z * 0.17) * 0.9 + Math.sin(x * 0.07 + 1.3) * Math.sin(z * 0.09 + 0.4) * 2.4 + Math.sin(x * 0.031 + 2) * Math.cos(z * 0.027) * 6 * far;
  const land = hills * (0.1 + e * 1.7) + e * 2.4 + far * 5;
  const k = lakeK(x, z);
  return land * (1 - k) + (-1.9) * k;
}

const SEASON = {
  spring: { grass: [0.29, 0.58, 0.37], blade: ['#5fae4a', '#79c25c'], flowers: 520, leaves: null },
  summer: { grass: [0.285, 0.58, 0.34], blade: ['#4f9a3f', '#63ad4c'], flowers: 320, leaves: null },
  autumn: { grass: [0.21, 0.5, 0.35], blade: ['#8f9a3f', '#b0933d', '#6f9440'], flowers: 90, leaves: ['#e08a2e', '#d4552f', '#e6b93a'] },
  winter: { grass: [0.55, 0.12, 0.9], blade: ['#d9cfa8', '#c9c39c'], flowers: 0, leaves: null },
};
const EMOJI = { happy: '😊', joyful: '😄', excited: '🤩', content: '😌', proud: '😎', peaceful: '😌', loved: '🥰', playful: '😜', curious: '🤔', grateful: '🙏',
  inspired: '✨', calm: '😌', cozy: '☺️', sad: '😢', lonely: '🥺', bored: '😑', angry: '😠', anxious: '😰', frustrated: '😤', scared: '😨', grumpy: '😒',
  tired: '🥱', sleepy: '😴', hungry: '🤤', silly: '🤪', thoughtful: '🤔', nostalgic: '🥹', hopeful: '🌟', relaxed: '😌', determined: '💪', creative: '🎨', amazed: '😮' };

export function createWorld(container, tooltip, opts = {}) {
  env.season = SEASON[opts.season] ? opts.season : 'summer';
  env.artKey = opts.key || '';
  const S = SEASON[env.season];
  const small = container.clientWidth < 600;
  env.lite = !!opts.lite || small;      // phones and the server camera get lighter trees

  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, small ? 1.5 : 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.NeutralToneMapping; renderer.toneMappingExposure = 0.92;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog('#bfe3f5', 60, 300);
  const camera = new THREE.PerspectiveCamera(42, 16 / 10, 0.2, 900);
  const HOME = new THREE.Vector3(-15, 10, 23);
  camera.position.set(-70, 60, 95);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.6, 0); controls.enableDamping = true; controls.dampingFactor = 0.07;
  controls.maxPolarAngle = Math.PI / 2 - 0.06; controls.minDistance = 4; controls.maxDistance = 90;
  controls.autoRotate = false; controls.autoRotateSpeed = 0.3;
  let idleAt = Infinity, intro = 0, focus = null;
  controls.addEventListener('start', () => { controls.autoRotate = false; idleAt = Infinity; intro = 1; focus = null; camGoal = null; });
  controls.addEventListener('end', () => { idleAt = performance.now() + 25000; });

  // post-processing: ambient shading in creases, soft glow on lights, then a gentle colour grade
  let composer = null, bloom = null, gtao = null;
  const Grade = { uniforms: { tDiffuse: { value: null }, warmth: { value: 0.5 }, vig: { value: 0.32 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform float warmth; uniform float vig; varying vec2 vUv;
      void main(){ vec4 c = texture2D(tDiffuse, vUv); float l = dot(c.rgb, vec3(0.299, 0.587, 0.114));
        c.rgb = mix(vec3(l), c.rgb, 1.14);                                   // a little more colour
        c.rgb = (c.rgb - 0.5) * 1.06 + 0.5;                                  // a little more contrast
        c.rgb *= mix(vec3(1.0), vec3(1.035, 1.0, 0.955), warmth);            // warm highlights
        c.rgb += (1.0 - l) * vec3(-0.006, 0.0, 0.016);                       // cool shadows
        vec2 d = vUv - 0.5; c.rgb *= 1.0 - vig * smoothstep(0.25, 0.95, dot(d, d) * 2.2);
        gl_FragColor = vec4(clamp(c.rgb, 0.0, 1.0), c.a); }` };
  if (!opts.lite) try {  // lite: no post-processing (the server's camera has no graphics card)
    const rt = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: small ? 2 : 4 });
    composer = new EffectComposer(renderer, rt);
    composer.addPass(new RenderPass(scene, camera));
    if (!small) { gtao = new GTAOPass(scene, camera, 4, 4); gtao.updateGtaoMaterial({ radius: 0.9, distanceExponent: 1.4, thickness: 1.2, scale: 1.25, samples: 10 }); gtao.blendIntensity = 0.85; composer.addPass(gtao);
      const aoRender = gtao.render.bind(gtao), hidden = [];   // sprites and particles must not cast ambient shade
      gtao.render = (...a) => { hidden.length = 0; scene.traverseVisible(o => { if (o.isSprite || o.isPoints || o.isLineSegments || o.userData.puff || o.userData.noAO) hidden.push(o); }); hidden.forEach(o => o.visible = false); aoRender(...a); hidden.forEach(o => o.visible = true); }; }
    bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.35, 0.7, 1.0);
    composer.addPass(bloom); composer.addPass(new OutputPass()); composer.addPass(new ShaderPass(Grade));
  } catch (e) { console.warn('Post-processing unavailable', e); composer = null; }
  else if (opts.film) try {  // the video camera: no heavy effects, but smooth edges, soft glow and the same colour grade
    composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType }));
    composer.addPass(new RenderPass(scene, camera));
    if (opts.film.glow) { bloom = new UnrealBloomPass(new THREE.Vector2(128, 128), 0.35, 0.7, 1.0); composer.addPass(bloom); }
    composer.addPass(new OutputPass()); composer.addPass(new FXAAPass()); composer.addPass(new ShaderPass(Grade));
  } catch (e) { console.warn('Film effects unavailable', e); composer = null; }

  // ---------------------------------------------------------------- sky
  const skyU = { top: { value: C('#3f8fd8') }, horizon: { value: C('#bfe3f5') }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, sunCol: { value: C('#fff2c0') }, glow: { value: 1 } };
  const sky = new THREE.Mesh(new THREE.SphereGeometry(700, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false, uniforms: skyU,
    vertexShader: 'varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform vec3 top; uniform vec3 horizon; uniform vec3 sunDir; uniform vec3 sunCol; uniform float glow; varying vec3 vDir;
      void main(){ vec3 d = normalize(vDir); float h = clamp(d.y, 0.0, 1.0);
        vec3 col = mix(horizon, top, pow(h, 0.55)); col = mix(col, horizon * 0.85, clamp(-d.y * 4.0, 0.0, 1.0));
        float s = max(dot(d, sunDir), 0.0); col += sunCol * (pow(s, 24.0) * 0.28 + pow(s, 5.0) * 0.12) * glow;
        gl_FragColor = vec4(col, 1.0); }`,
  }));
  sky.renderOrder = -10; scene.add(sky);
  // the same sky lights every surface (soft reflections, coloured shade)
  const pmrem = new THREE.PMREMGenerator(renderer), envScene = new THREE.Scene(); let envRT = null, envAt = -99, envKey = '';
  envScene.add(new THREE.Mesh(new THREE.SphereGeometry(50, 24, 12), sky.material));
  function refreshEnv(t, key) {
    if (key === envKey || t - envAt < 1.5) return;
    envKey = key; envAt = t; const old = envRT; envRT = pmrem.fromScene(envScene, 0.03, 0.1, 100); scene.environment = envRT.texture; old?.dispose();
  }
  const sunBall = new THREE.Mesh(geos.smooth, new THREE.MeshBasicMaterial({ color: C('#fff2b0').multiplyScalar(3), fog: false })); sunBall.scale.setScalar(26); scene.add(sunBall);
  const moon = new THREE.Mesh(geos.smooth, new THREE.MeshBasicMaterial({ color: C('#eef1ff').multiplyScalar(1.6), fog: false })); moon.scale.setScalar(20); scene.add(moon);
  const r0 = rng(5);
  const sp = new Float32Array(1400 * 3);
  for (let i = 0; i < 1400; i++) { const v = new THREE.Vector3().setFromSphericalCoords(600, Math.acos(r0() * 0.97), r0() * 6.28); sp.set([v.x, v.y, v.z], i * 3); }
  const sgeo = new THREE.BufferGeometry(); sgeo.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  const stars = new THREE.Points(sgeo, new THREE.PointsMaterial({ color: C('#ffffff').multiplyScalar(2), size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0, fog: false, depthWrite: false })); scene.add(stars);

  const hemi = new THREE.HemisphereLight('#dff3ff', '#7fae62', 1.0); scene.add(hemi);
  const sun = new THREE.DirectionalLight('#fff3d6', 2.4);
  sun.castShadow = true; sun.shadow.mapSize.set(small ? 1024 : 4096, small ? 1024 : 4096);
  Object.assign(sun.shadow.camera, { left: -27, right: 27, top: 24, bottom: -24, near: 1, far: 170 });
  sun.shadow.bias = -0.0003; sun.shadow.normalBias = 0.04; sun.shadow.radius = 4;
  scene.add(sun, sun.target);

  // ---------------------------------------------------------------- terrain
  const sand = C('#dccb9b'), rockC = C(env.season === 'winter' ? '#e9eef0' : '#8f9a86'), c = new THREE.Color();
  function groundColor(x, z, y, out) {
    const n = Math.sin(x * 0.13 + Math.sin(z * 0.09) * 2) * Math.cos(z * 0.11 + Math.sin(x * 0.07)), m = Math.sin(x * 0.6 + z * 0.4) * Math.sin(z * 0.7 - x * 0.3);
    out.setHSL(S.grass[0] + n * 0.018 - Math.min(0.05, Math.max(0, y) * 0.006), S.grass[1] + n * 0.05, S.grass[2] + n * 0.035 + m * 0.012 - Math.min(0.1, Math.max(0, y) * 0.008));
    return out.lerp(sand, smooth(0.02, 0.5, lakeK(x, z))).lerp(rockC, smooth(11, 17, y));
  }
  const tg = new THREE.PlaneGeometry(440, 440, 220, 220); tg.rotateX(-Math.PI / 2);
  const pos = tg.attributes.position, cols = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i), y = groundY(x, z);
    pos.setY(i, y); groundColor(x, z, y, c); cols.set([c.r, c.g, c.b], i * 3);
  }
  tg.setAttribute('color', new THREE.BufferAttribute(cols, 3)); tg.computeVertexNormals();
  const ground = new THREE.Mesh(tg, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, envMapIntensity: 0.6 }));
  ground.receiveShadow = true; scene.add(ground);

  // lake
  const waterMat = sharedWater(), rip = ripples();
  const lake = new THREE.Mesh(new THREE.PlaneGeometry(40, 32, 1, 1), waterMat); lake.rotation.x = -Math.PI / 2; lake.position.set(LAKE.x, WATER_Y, LAKE.z); lake.receiveShadow = true; scene.add(lake);
  const dock = new THREE.Group();
  for (let i = 0; i < 8; i++) { part(dock, 'box', '#a87645', [1.6, 0.08, 0.46], [0, 0.14, i * 0.52], [0, (r0() - 0.5) * 0.06, 0]); if (i % 3 === 1) for (const x of [-0.75, 0.75]) part(dock, 'cyl', '#7a5230', [0.14, 1.8, 0.14], [x, -0.4, i * 0.52]); }
  dock.position.set(LAKE.x - 5, WATER_Y, LAKE.z + 8.2); scene.add(dock);
  const boat = new THREE.Group(); B.boat(boat, { name: '' }, r0); boat.position.set(LAKE.x - 1, WATER_Y - 0.1, LAKE.z + 3); boat.rotation.y = 0.6; scene.add(boat);
  const lily = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.4, 0.4, 0.04, 9), mat('#5fae4f'), 26); const dummy = new THREE.Object3D();
  for (let i = 0; i < 26; i++) { const a = r0() * 6.28, d = 3 + r0() * 5; dummy.position.set(LAKE.x + Math.cos(a) * d * 1.2, WATER_Y + 0.06, LAKE.z + Math.sin(a) * d); dummy.rotation.set(0, r0() * 6, 0); dummy.scale.setScalar(0.6 + r0() * 0.8); dummy.updateMatrix(); lily.setMatrixAt(i, dummy.matrix); }
  scene.add(lily);

  // mountains on the horizon
  const mcol = [C('#6f8a8f'), C('#8fa3a5'), C('#f4f8fb')];
  for (let i = 0; i < 34; i++) {
    const far = i >= 16, a = i / (far ? 18 : 16) * 6.28 + r0() * 0.3, d = (far ? 215 : 150) + r0() * 40, h = (far ? 60 : 38) + r0() * 34, w = (far ? 90 : 60) + r0() * 40;
    const g = new THREE.ConeGeometry(w / 2, h, 7, 4); const p = g.attributes.position, mc = new Float32Array(p.count * 3);
    for (let j = 0; j < p.count; j++) { const y = p.getY(j) / h + 0.5; if (y < 0.95 && y > 0.05) { p.setX(j, p.getX(j) + (r0() - 0.5) * w * 0.14); p.setZ(j, p.getZ(j) + (r0() - 0.5) * w * 0.14); } const cc = y > (env.season === 'winter' ? 0.3 : 0.62) ? mcol[2] : y > 0.3 ? mcol[1] : mcol[0]; mc.set([cc.r, cc.g, cc.b], j * 3); }
    g.setAttribute('color', new THREE.BufferAttribute(mc, 3)); g.computeVertexNormals();
    const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 1 })); m.position.set(Math.cos(a) * d, h / 2 - 3, Math.sin(a) * d); scene.add(m);
  }

  // grass, wildflowers, forest. His home (the 16 x 10 grid and a little around it) is short, trodden lawn; the tall
  // meadow grass grows around it, wildest where he never goes.
  const yardD = (x, z) => Math.hypot(Math.max(0, Math.abs(x) - GW + 1), Math.max(0, Math.abs(z) - GH + 0.5));
  const yardK = (x, z) => 1 - smooth(0.5, 4.5, yardD(x, z));
  let grassShare = 1;
  const N = Math.round((small ? 22000 : 72000) * (env.season === 'winter' ? 0.25 : 1));
  const bladeGeo = new THREE.PlaneGeometry(0.11, 0.62, 1, 4); bladeGeo.translate(0, 0.31, 0);
  { const p = bladeGeo.attributes.position, nrm = bladeGeo.attributes.normal, bc = new Float32Array(p.count * 3);
    for (let i = 0; i < p.count; i++) { const t = p.getY(i) / 0.62; p.setX(i, p.getX(i) * (1 - t * 0.88)); p.setZ(i, t * t * 0.2); nrm.setXYZ(i, 0, 1, 0.25 - t * 0.2); const k = 0.5 + t * 0.62; bc.set([k, k, k], i * 3); }
    bladeGeo.setAttribute('color', new THREE.BufferAttribute(bc, 3)); }
  const grass = new THREE.InstancedMesh(bladeGeo, windy(new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 1, vertexColors: true, side: THREE.DoubleSide, envMapIntensity: 0.5 }), 'sway', 0.3), N);
  grass.receiveShadow = true; grass.frustumCulled = false;
  const blades = new Float32Array(N * 5), bladeCol = new Float32Array(N * 3), tint = new THREE.Color(); let nb = 0;
  for (let i = 0; i < N * 4 && nb < N; i++) {
    const near = i % 5 !== 0, x = (r0() - 0.5) * (near ? 84 : 170), z = (r0() - 0.5) * (near ? 68 : 170), y = groundY(x, z);
    if (lakeK(x, z) > 0.04 || y > 9) continue;
    const yk = yardK(x, z), clump = 0.55 + 0.45 * Math.sin(x * 0.9 + Math.sin(z * 0.7) * 2) * Math.sin(z * 0.8);   // tufts and thinner patches
    if (r0() > (0.35 + clump * 0.65) * (1 - yk * 0.35)) continue;
    const wild = smooth(1, 12, yardD(x, z));                                  // taller the further from home
    const h = (0.55 + r0() * 0.8) * (0.8 + clump * 0.5) * THREE.MathUtils.lerp(1.05 + wild * 0.3, 0.36 + r0() * 0.16, yk);
    blades.set([x, y, z, r0() * 6.28, h], nb * 5);
    groundColor(x, z, y, c).lerp(tint.set(S.blade[Math.floor(r0() * S.blade.length)]), 0.35 - yk * 0.12).multiplyScalar(0.98 + r0() * 0.2); bladeCol.set([c.r, c.g, c.b], nb * 3); nb++;
  }
  scene.add(grass);

  // his trails: worn earth between the things he built (the shortest network joining them all) and a trodden patch
  // around each one, drawn on a thin layer that lies on the ground of his home
  const TX = 46, TZ = 32, T0 = [-TX / 2, -TZ / 2 - 1.5], TPX = 16, worn = document.createElement('canvas');
  worn.width = TX * TPX; worn.height = TZ * TPX;
  const wornTex = new THREE.CanvasTexture(worn); wornTex.colorSpace = THREE.SRGBColorSpace; wornTex.anisotropy = 4;
  const wg = new THREE.PlaneGeometry(TX, TZ, TX * 2, TZ * 2); wg.rotateX(-Math.PI / 2); wg.translate(T0[0] + TX / 2, 0, T0[1] + TZ / 2);
  { const p = wg.attributes.position; for (let i = 0; i < p.count; i++) p.setY(i, groundY(p.getX(i), p.getZ(i)) + 0.05); wg.computeVertexNormals(); }
  const trails = new THREE.Mesh(wg, new THREE.MeshStandardMaterial({ map: wornTex, transparent: true, depthWrite: false, roughness: 1, envMapIntensity: 0.4, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
  trails.receiveShadow = true; trails.userData.noAO = true; trails.renderOrder = -1; scene.add(trails);
  let trailSegs = [];
  function joinUp(pts) {   // Prim's minimum spanning tree: every spot reachable, with as little trodden ground as possible
    const segs = [], inTree = [0], left = pts.map((_, i) => i).slice(1);
    while (left.length) {
      let best = null;
      for (const a of inTree) for (const [j, b] of left.entries()) { const d = Math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1]); if (!best || d < best[0]) best = [d, a, j]; }
      const b = left.splice(best[2], 1)[0]; inTree.push(b); segs.push([pts[best[1]][0], pts[best[1]][1], pts[b][0], pts[b][1]]);
    }
    return segs;
  }
  function segDist(x, z, [ax, az, bx, bz]) {
    const dx = bx - ax, dz = bz - az, t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1)));
    return Math.hypot(x - ax - dx * t, z - az - dz * t);
  }
  function drawTrails(spots) {
    const x = worn.getContext('2d'), u = v => v * TPX, px = v => (v - T0[0]) * TPX, pz = v => (v - T0[1]) * TPX;
    const dirt = env.season === 'winter' ? '232,236,240' : env.season === 'autumn' ? '138,112,74' : '146,120,80';
    x.clearRect(0, 0, worn.width, worn.height); x.lineCap = 'round'; x.lineJoin = 'round';
    for (const [w, a] of [[2.1, 0.12], [1.5, 0.2], [0.95, 0.3], [0.5, 0.22]]) {     // soft edges that work in every browser
      x.strokeStyle = `rgba(${dirt},${a})`; x.lineWidth = u(w); x.beginPath();
      for (const s of trailSegs) { x.moveTo(px(s[0]), pz(s[1])); x.lineTo(px(s[2]), pz(s[3])); }
      x.stroke();
    }
    for (const [sx, sz, r] of spots) {
      const g = x.createRadialGradient(px(sx), pz(sz), 0, px(sx), pz(sz), u(r + 1.1));
      g.addColorStop(0, `rgba(${dirt},0.5)`); g.addColorStop(0.55, `rgba(${dirt},0.32)`); g.addColorStop(1, `rgba(${dirt},0)`);
      x.fillStyle = g; x.beginPath(); x.arc(px(sx), pz(sz), u(r + 1.1), 0, 6.3); x.fill();
    }
    wornTex.needsUpdate = true;
  }
  function layGrass(clear) {   // skip blades where Gino has put something or walks all the time
    trailSegs = clear.length > 1 ? joinUp(clear) : []; drawTrails(clear);
    let k = 0;
    for (let i = 0; i < nb; i++) {
      const x = blades[i * 5], z = blades[i * 5 + 2]; let ok = true, sc = blades[i * 5 + 4];
      for (const [cx, cz, cr] of clear) { const d = Math.hypot(x - cx, z - cz); if (d < cr) { ok = false; break; } if (d < cr + 1.2) sc *= 0.55 + 0.45 * (d - cr) / 1.2; }
      if (!ok) continue;
      let td = 9; for (const s of trailSegs) td = Math.min(td, segDist(x, z, s));
      if (td < 0.45) continue;
      if (td < 1.3) sc *= 0.5 + 0.5 * (td - 0.45) / 0.85;
      dummy.position.set(x, blades[i * 5 + 1] - 0.02, z); dummy.rotation.set(0, blades[i * 5 + 3], 0); dummy.scale.set(sc, sc, sc); dummy.updateMatrix();
      grass.setMatrixAt(k, dummy.matrix); grass.setColorAt(k, c.fromArray(bladeCol, i * 3)); k++;
    }
    grass.count = Math.round(k * grassShare); grass.userData.full = k; grass.instanceMatrix.needsUpdate = true; if (grass.instanceColor) grass.instanceColor.needsUpdate = true;
  }
  if (S.flowers) {
    const fl = new THREE.InstancedMesh(new THREE.SphereGeometry(0.1, 8, 6).scale(1, 0.7, 1).translate(0, 0.5, 0), windy(new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.7 }), 'sway', 0.3), S.flowers);
    const fc = ['#f27ca0', '#f6c833', '#ffffff', '#b78cf0', '#f2603d', '#7ab8f5']; let k = 0;
    for (let i = 0; i < S.flowers * 3 && k < S.flowers; i++) { const x = (r0() - 0.5) * 90, z = (r0() - 0.5) * 80; if (lakeK(x, z) > 0.05 || groundY(x, z) > 8) continue; dummy.position.set(x, groundY(x, z), z); dummy.rotation.set(0, 0, 0); dummy.scale.setScalar(0.7 + r0() * 0.8); dummy.updateMatrix(); fl.setMatrixAt(k, dummy.matrix); fl.setColorAt(k, c.set(fc[Math.floor(r0() * fc.length)])); k++; }
    fl.count = k; fl.instanceColor.needsUpdate = true; scene.add(fl);
  }
  for (let i = 0; i < 150; i++) {
    const a = r0() * 6.28, d = 27 + r0() * 75, x = Math.cos(a) * d * 1.2, z = Math.sin(a) * d;
    if (lakeK(x, z) > 0.02) continue;
    const g = new THREE.Group(), t = r0(); (t < 0.45 ? B.pine : t < 0.8 ? B.tree : t < 0.9 ? B.bush : B.rock)(g, { name: '', far: true }, r0);
    g.position.set(x, groundY(x, z) - 0.05, z); g.rotation.y = r0() * 6; g.scale.setScalar(0.9 + r0() * 1.5); scene.add(g);
  }
  for (let i = 0; i < 40; i++) { // reeds on the lake shore
    const a = r0() * 6.28, x = LAKE.x + Math.cos(a) * LAKE.r * 0.93 / 0.8 * (0.9 + r0() * 0.08), z = LAKE.z + Math.sin(a) * LAKE.r * 0.93 * (0.9 + r0() * 0.08);
    const g = new THREE.Group(); for (let j = 0; j < 4; j++) { const h = 0.9 + r0() * 0.8, px = (r0() - 0.5) * 0.6, pz = (r0() - 0.5) * 0.6; part(g, 'cyl', '#7fae52', [0.05, h, 0.05], [px, h / 2, pz]); part(g, 'cyl', '#6b4423', [0.1, 0.28, 0.1], [px, h, pz]); }
    g.position.set(x, Math.max(groundY(x, z), WATER_Y - 0.2), z); scene.add(g);
  }

  // clouds
  const clouds = [], cloudMat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 1, vertexColors: true, transparent: true, opacity: 0.95, envMapIntensity: 1.3 });
  for (let i = 0; i < 22; i++) {
    const g = new THREE.Group();
    for (let j = 0; j < 7; j++) { const e = 1 - Math.abs(j - 3) / 4.5; const p = part(g, 'puff', cloudMat, [(6 + r0() * 5) * (0.6 + e * 0.6), (3.2 + r0() * 2.5) * (0.5 + e * 0.8), 5 + r0() * 3], [j * 3.1 - 9, e * 1.6 + r0(), (r0() - 0.5) * 4], [0, r0() * 6, 0]); p.castShadow = false; p.receiveShadow = false; }
    g.position.set((r0() - 0.5) * 380, 42 + r0() * 22, (r0() - 0.5) * 380); g.scale.setScalar(0.8 + r0() * 1.4); scene.add(g); clouds.push(g);
  }

  // rain / snow / falling leaves
  const RN = small ? 700 : 1600, rainPos = new Float32Array(RN * 6), rainSeed = new Float32Array(RN * 3);
  for (let i = 0; i < RN; i++) rainSeed.set([(r0() - 0.5) * 70, r0() * 40, (r0() - 0.5) * 70], i * 3);
  const rainGeo = new THREE.BufferGeometry(); rainGeo.setAttribute('position', new THREE.BufferAttribute(rainPos, 3));
  const rain = new THREE.LineSegments(rainGeo, new THREE.LineBasicMaterial({ color: '#cfe6ff', transparent: true, opacity: 0 })); rain.frustumCulled = false; scene.add(rain);
  const FN = 900, flakePos = new Float32Array(FN * 3), flakeSeed = new Float32Array(FN * 4);
  for (let i = 0; i < FN; i++) flakeSeed.set([(r0() - 0.5) * 70, r0() * 30, (r0() - 0.5) * 70, r0() * 6], i * 4);
  const flakeGeo = new THREE.BufferGeometry(); flakeGeo.setAttribute('position', new THREE.BufferAttribute(flakePos, 3));
  const flakes = new THREE.Points(flakeGeo, new THREE.PointsMaterial({ color: '#ffffff', size: 0.22, transparent: true, opacity: 0, depthWrite: false })); flakes.frustumCulled = false; scene.add(flakes);

  // birds, butterflies / fireflies
  const birds = [];
  for (let i = 0; i < 7; i++) {
    const g = new THREE.Group(), wings = [];
    for (const s of [-1, 1]) { const piv = new THREE.Group(); g.add(piv); const w = part(piv, 'box', '#3a3f4a', [0.9, 0.04, 0.35], [0, 0, s * 0.45], [0, s * 0.3, 0]); w.castShadow = false; wings.push(piv); }
    part(g, 'sphere', '#3a3f4a', [0.6, 0.2, 0.2], [0, 0, 0]).castShadow = false;
    g.userData = { a: r0() * 6.28, r: 18 + r0() * 40, h: 14 + r0() * 14, s: 0.12 + r0() * 0.12, wings, cx: (r0() - 0.5) * 40, cz: (r0() - 0.5) * 40 }; scene.add(g); birds.push(g);
  }
  const flies = [];
  for (let i = 0; i < 22; i++) {
    const g = new THREE.Group(), m = new THREE.MeshBasicMaterial({ color: '#f6ff9a', transparent: true, side: THREE.DoubleSide }), wings = [];
    for (const s of [-1, 1]) { const piv = new THREE.Group(); g.add(piv); const w = new THREE.Mesh(geos.plane, m); w.scale.set(0.09, 0.12, 1); w.position.x = s * 0.045; w.rotation.x = -Math.PI / 2; piv.add(w); wings.push(piv); }
    const dot = new THREE.Mesh(geos.sphere, m); dot.scale.setScalar(0.09); g.add(dot);
    g.userData = { a: r0() * 6.28, r: 3 + r0() * 14, h: 0.6 + r0() * 1.6, s: 0.1 + r0() * 0.25, c: new THREE.Color().setHSL(r0(), 0.85, 0.62), m, wings, dot }; scene.add(g); flies.push(g);
  }

  // ---------------------------------------------------------------- Gino and his things
  const gino = buildGino(); scene.add(gino);
  const G = gino.userData;
  const itemsGroup = new THREE.Group(); scene.add(itemsGroup);
  const itemObjs = new Map(); let ponds = [];
  let state = { pos: [7, 5], asleep: false, activity: '', habitat: [] }, placed = false;
  const target = new THREE.Vector3(), anchor = new THREE.Vector3();

  // Between his brain's decisions Gino lives a little life of his own: he wanders to the things he built and does
  // something there. `anchor` is where his brain put him; `target` is where his feet are heading right now.
  const R = { on: opts.roam !== false && !opts.lite, cur: 'idle', next: 'idle', aw: 0, until: 0, hold: 8, arrived: true, face: null, label: '', last: [], pond: null, n: 0, sincePond: 9, sig: '', zc: null, pose: null };
  const ACT = { pond: ['swim', 'paddling around the'], bench: ['sit', 'sitting by the'], picnic: ['sit', 'sitting at the'], campfire: ['sit', 'warming up by the'], table: ['sit', 'sitting at the'],
    tent: ['sit', 'sitting outside the'], house: ['sit', 'sitting outside the'], hammock: ['nap', 'dozing by the'], bed: ['nap', 'having a quick doze on the'], flowers: ['sniff', 'sniffing the'],
    mushroom: ['sniff', 'sniffing the'], bush: ['sniff', 'sniffing the'], beehive: ['sniff', 'carefully sniffing the'], garden: ['graze', 'nibbling in the'], pumpkins: ['graze', 'nibbling at the'],
    fruit_tree: ['graze', 'munching under the'], tree: ['scratch', 'scratching his back on the'], pine: ['scratch', 'scratching his back on the'], rock: ['scratch', 'scratching his back on the'],
    well: ['look', 'peering into the'], board: ['look', 'admiring'], piano: ['dance', 'dancing by the'], swing: ['hops', 'bouncing around the'], fountain: ['hops', 'splashing about by the'] };
  const FREE = [['roll', 'rolling in the grass'], ['graze', 'grazing'], ['zoom', 'having the zoomies'], ['sit', 'sitting in the sun'], ['stretch', 'having a big stretch'], ['look', 'watching the birds'], ['hops', 'hopping about'], ['nap', 'dozing in the grass'], ['roll', 'rolling in the grass']];
  const BIG = { house: 2.0, tent: 1.7, fountain: 1.6, garden: 1.5, picnic: 1.4, windmill: 1.4, gallery: 1.4, bed: 1.3, piano: 1.3, pumpkins: 1.2, campfire: 1.2 };
  const any = a => a[Math.floor(Math.random() * a.length)];
  // Cute poses: now and then Gino stops, turns to whoever is watching and strikes a pose that fits his mood.
  // hearts: little hops with hearts floating up; orange: balances an orange on his head.
  const POSES = {
    hop: { act: 'idle', name: 'a happy hop', hearts: true }, roll: { act: 'roll', name: 'a belly-up wiggle' },
    orange: { act: 'sit', name: 'balancing an orange on his head', orange: true }, stretch: { act: 'stretch', name: 'a big proud stretch' },
    sit: { act: 'sit', name: 'sitting pretty' }, dance: { act: 'dance', name: 'a little dance' }, curl: { act: 'nap', name: 'a sleepy curl-up' },
    sniff: { act: 'sniff', name: 'a curious sniff' } };
  const MOOD_POSES = [
    [/happy|joy|love|grateful|excit|hope|amaz/, ['hop', 'hop', 'dance']], [/playful|silly|bored|goof/, ['roll', 'roll', 'hop']],
    [/content|peace|calm|relax|cozy|nostalg/, ['orange', 'orange', 'sit']], [/proud|determin|confident/, ['stretch', 'stretch', 'sit']],
    [/tired|sleepy/, ['curl']], [/curious|thought|wonder/, ['sniff', 'sit']], [/creative|inspired/, ['dance', 'orange']],
    [/sad|lonely|anxious|scared|grumpy|frustrat|angry/, ['sit']] ];
  function poseFor(mood) {
    const m = (mood || '').toLowerCase(), hit = MOOD_POSES.find(([re]) => re.test(m));
    return POSES[any(hit ? hit[1] : Object.keys(POSES).filter(k => k !== 'curl'))];
  }
  function strikePose(p = poseFor(state.emotion)) {   // right where he is, facing the camera
    target.copy(gino.position).setY(0); R.next = p.act; R.pose = p; R.face = camera.position; R.pond = null; R.arrived = false;
    R.label = `striking a cute pose: ${p.name}`; R.hold = p.act === 'stretch' ? 6 : 8 + Math.random() * 4;
  }
  function actFor(text, onPond) {
    const a = (text || '').toLowerCase();
    if (/\bpos(e|ing)\b|cute|show(ing)? off|selfie/.test(a) && R.on && !onPond) return 'pose';
    if (/munch|eat|forag|graz|snack|nibbl/.test(a)) return 'graze';
    if (!R.on) return 'idle';
    if (onPond) return 'swim';
    if (/nap|doz|rest|snooz/.test(a)) return 'nap';
    if (/danc|music|piano|sing/.test(a)) return 'dance';
    if (/play|celebrat|excit|zoom/.test(a)) return 'hops';
    if (/sit|relax|loung|chill/.test(a)) return 'sit';
    if (/paint|draw|creat|writ|read|think|look|watch|star|build|plac|admir/.test(a)) return 'look';
    return 'idle';
  }
  function goHome(hold) {
    target.copy(anchor); R.pond = ponds.find(o => Math.hypot(o.position.x - anchor.x, o.position.z - anchor.z) < 0.1) || null;
    R.next = actFor(state.activity, !!R.pond); R.label = ''; R.hold = hold; R.arrived = false; R.face = null; R.pose = null; if (R.pond) R.sincePond = 0;
    if (R.next === 'pose') { const p = poseFor(state.emotion); R.next = p.act; R.pose = p; R.face = camera.position; }
  }
  function pickNext() {
    R.sincePond++; R.pose = null;
    if (++R.n % 4 === 0) return goHome(22);
    if (Math.random() < 0.16) return strikePose();
    const spots = [...itemObjs.values(), ...(board ? [board] : [])].filter(o => !R.last.includes(o) && (o.userData.kind !== 'pond' || R.sincePond > 3));
    R.face = null; R.pond = null; R.arrived = false;
    if (!spots.length || Math.random() < 0.38) {
      target.set((Math.random() - 0.5) * 30, 0, (Math.random() - 0.5) * 18);
      [R.next, R.label] = any(FREE); R.hold = R.next === 'zoom' ? 9 : R.next === 'stretch' ? 4 : 9 + Math.random() * 9;
    } else {
      const o = any(spots), kind = o.userData.kind, [act, words] = ACT[kind] || ['look', 'admiring the'], sc = o.userData.grow || 1;
      R.last = [o, ...R.last].slice(0, 3);
      if (kind === 'pond') { target.set(o.position.x, 0, o.position.z); R.pond = o; R.sincePond = 0; }
      else if (kind === 'board') { target.copy(boardFront()).add(v3.set((Math.random() - 0.5) * 1.6, 0, 0)); R.face = o.position; }
      else { const a = Math.random() * 6.283, r = (BIG[kind] || 1.05) * sc + 0.35; target.set(o.position.x + Math.cos(a) * r, 0, o.position.z + Math.sin(a) * r); R.face = o.position; }
      R.next = act; R.label = `${words} ${o.userData.item?.name || kind}`; R.hold = 10 + Math.random() * 10;
    }
  }
  let weatherOverride = null;
  let follow = false, timeMode = 'auto', weather = 'clear', lastEmote = null, hop = 0, heartT = -9;
  const W = { cloud: 0.25, rain: 0, snow: 0, fog: 0 };

  function dispose(o) { o.traverse(n => { if (n.isSprite) { n.material.map?.dispose(); n.material.dispose(); } }); }

  // his drawings, shown on easels and gallery walls
  const artTex = new Map();
  function loadArt(file) {
    if (artTex.has(file)) return artTex.get(file);
    const tex = new THREE.CanvasTexture(Object.assign(document.createElement('canvas'), { width: 512, height: 512 })); tex.colorSpace = THREE.SRGBColorSpace;
    artTex.set(file, tex);
    fetch(file.startsWith('/') ? file : `/creations/${file}`, file.startsWith('/') ? {} : { headers: { 'x-gino-key': env.artKey } }).then(r => r.ok ? r.text() : Promise.reject()).then(svg => {
      if (!/<svg[^>]*\swidth=/.test(svg)) svg = svg.replace('<svg', '<svg width="512" height="512"');
      if (!/xmlns=/.test(svg)) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
      const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' })), img = new Image();
      img.onload = () => { const x = tex.image.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 512, 512); x.drawImage(img, 0, 0, 512, 512); tex.needsUpdate = true; URL.revokeObjectURL(url); };
      img.src = url;
    }).catch(() => {});
    return tex;
  }
  function hangArt() {
    let easel = 0;
    for (const o of itemObjs.values()) {
      const base = o.userData.kind === 'easel' ? easel++ : 0;
      o.traverse(m => { if (m.userData.artSlot === undefined) return; const f = env.art[(base + m.userData.artSlot) % Math.max(1, env.art.length)]; const t = f ? loadArt(f) : null; if (m.material.map !== t) { m.material.map = t; m.material.needsUpdate = true; } });
    }
  }

  // ---------------------------------------------------------------- Gino's creations board (the live page turns it on)
  // A little wooden notice board at the back of his meadow where his drawings and poems hang. Visitors can look
  // and read; nothing here sends anything to Gino.
  const BOARD_AT = new THREE.Vector3(-5, 0, -12.2), BW = 1024, BH = 640;
  let board = null, boardFace = null, boardTex = null, boardItems = [], boardRects = [], boardSig = '';
  const boardImg = new Map();
  function buildBoard() {
    const g = new THREE.Group(); g.userData = { kind: 'board', item: { name: 'his creations board' } };
    g.position.set(BOARD_AT.x, groundY(BOARD_AT.x, BOARD_AT.z), BOARD_AT.z); g.rotation.y = 0.18;
    for (const x of [-2.15, 2.15]) { part(g, 'cyl', '#6e4a2c', [0.2, 3.7, 0.2], [x, 1.85, 0]); part(g, 'sphere', '#6e4a2c', [0.26, 0.26, 0.26], [x, 3.72, 0]); }
    part(g, 'box', '#8a5e37', [4.5, 2.75, 0.16], [0, 2.2, -0.04]);                                   // frame
    for (const s of [-1, 1]) part(g, 'box', '#9c4a32', [2.55, 0.12, 0.85], [s * 1.12, 3.86, 0.05], [0, 0, -s * 0.36]);   // little roof
    part(g, 'box', '#7a5230', [4.1, 0.1, 0.32], [0, 0.78, 0.14]);                                     // ledge
    for (const [x, c] of [[-1.6, '#e8a33d'], [-1.25, '#d6453d'], [1.4, '#9b6fd1'], [1.75, '#e8a33d']]) { part(g, 'cyl', '#5d8c3a', [0.04, 0.5, 0.04], [x, 0.25, 0.4]); part(g, 'sphere', c, [0.18, 0.12, 0.18], [x, 0.52, 0.4]); }
    const cv = Object.assign(document.createElement('canvas'), { width: BW, height: BH });
    boardTex = new THREE.CanvasTexture(cv); boardTex.colorSpace = THREE.SRGBColorSpace; boardTex.anisotropy = 8;
    boardFace = new THREE.Mesh(new THREE.PlaneGeometry(4.15, 4.15 * BH / BW), new THREE.MeshStandardMaterial({ map: boardTex, roughness: 0.95 }));
    boardFace.position.set(0, 2.2, 0.05); boardFace.receiveShadow = true; boardFace.userData.noAO = true; g.add(boardFace);
    g.traverse(n => { if (n.isMesh) n.castShadow = true; });
    scene.add(g); return g;
  }
  function wrap(x, text, w) {   // split text into lines that fit
    const out = [];
    for (const para of String(text).split('\n')) {
      let line = '';
      for (const word of para.split(/\s+/)) { const t = line ? line + ' ' + word : word; if (x.measureText(t).width > w && line) { out.push(line); line = word; } else line = t; }
      out.push(line);
    }
    return out;
  }
  function drawBoard() {
    const x = boardTex.image.getContext('2d'), r = rng(7);
    x.fillStyle = '#c8935a'; x.fillRect(0, 0, BW, BH);                                     // cork
    for (let i = 0; i < 2600; i++) { x.fillStyle = r() < 0.5 ? 'rgba(120,70,30,.18)' : 'rgba(255,230,190,.16)'; x.fillRect(r() * BW, r() * BH, 2 + r() * 4, 2 + r() * 3); }
    x.font = 'bold 40px Georgia, serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillStyle = '#fff7e8'; x.strokeStyle = '#5b4a38'; x.lineWidth = 4;
    x.beginPath(); x.roundRect(BW / 2 - 200, 14, 400, 60, 12); x.fill(); x.stroke();
    x.fillStyle = '#3b2e22'; x.fillText("Gino's creations", BW / 2, 46);
    boardRects = [];
    const items = boardItems.slice(0, 8), n = items.length;
    if (!n) {
      x.save(); x.translate(BW / 2, BH / 2 + 40); x.rotate(-0.03); x.fillStyle = '#fffdf6'; x.shadowColor = 'rgba(0,0,0,.3)'; x.shadowOffsetY = 6; x.shadowBlur = 8; x.fillRect(-260, -90, 520, 180); x.shadowColor = 'transparent';
      x.fillStyle = '#3b2e22'; x.font = 'italic 34px Georgia, serif'; x.fillText('Nothing pinned up yet.', 0, -24); x.font = 'italic 28px Georgia, serif'; x.fillStyle = '#7d6a55'; x.fillText('His drawings and poems will hang here.', 0, 28);
      x.fillStyle = '#d6453d'; x.beginPath(); x.arc(0, -82, 11, 0, 7); x.fill(); x.restore();
      boardTex.needsUpdate = true; return;
    }
    const cols = n <= 3 ? n : 4, rows = Math.ceil(n / cols), cw = (BW - 60) / cols, ch = (BH - 110) / rows;
    items.forEach((it, i) => {
      const c = i % cols, rw = Math.floor(i / cols), cx = 30 + cw * (c + 0.5), cy = 100 + ch * (rw + 0.5);
      const w = Math.min(cw - 34, rows > 1 ? 210 : 270), h = Math.min(ch - 26, rows > 1 ? 232 : 330), a = (r() - 0.5) * 0.09;
      x.save(); x.translate(cx, cy); x.rotate(a);
      x.shadowColor = 'rgba(40,20,5,.35)'; x.shadowOffsetX = 4; x.shadowOffsetY = 7; x.shadowBlur = 10;
      if (it.img) {
        x.fillStyle = '#fffdf6'; x.fillRect(-w / 2, -h / 2, w, h); x.shadowColor = 'transparent';
        const im = boardImg.get(it.img), s = w - 20, ih = h - 56;
        if (im?.complete && im.naturalWidth) { const k = Math.min(s / im.naturalWidth, ih / im.naturalHeight), dw = im.naturalWidth * k, dh = im.naturalHeight * k; x.drawImage(im, -dw / 2, -h / 2 + 10 + (ih - dh) / 2, dw, dh); }
        else { x.fillStyle = '#efe6d4'; x.fillRect(-s / 2, -h / 2 + 10, s, ih); }
        x.fillStyle = '#3b2e22'; x.font = 'italic 22px Georgia, serif'; x.textAlign = 'center';
        x.fillText(fit(x, it.title, w - 16), 0, h / 2 - 22);
      } else {
        x.fillStyle = it.kind === 'song' ? '#e9f1ff' : '#fff4c9'; x.fillRect(-w / 2, -h / 2, w, h); x.shadowColor = 'transparent';
        x.strokeStyle = 'rgba(80,120,190,.25)'; x.lineWidth = 2; for (let y = -h / 2 + 64; y < h / 2 - 8; y += 24) { x.beginPath(); x.moveTo(-w / 2 + 10, y); x.lineTo(w / 2 - 10, y); x.stroke(); }
        x.fillStyle = '#3b2e22'; x.textAlign = 'left'; x.font = 'bold 22px Georgia, serif';
        x.fillText(fit(x, (it.kind === 'song' ? '♪ ' : '') + it.title, w - 28), -w / 2 + 14, -h / 2 + 34);
        x.font = 'italic 17px Georgia, serif'; x.fillStyle = '#5b4a38';
        const lines = wrap(x, it.text || '', w - 28), max = Math.floor((h - 70) / 24);
        lines.slice(0, max).forEach((l, j) => x.fillText(j === max - 1 && lines.length > max ? '…' : l, -w / 2 + 14, -h / 2 + 60 + j * 24));
      }
      x.fillStyle = ['#d6453d', '#3f7fd6', '#e8a33d', '#4f9a3f'][i % 4]; x.beginPath(); x.arc(0, -h / 2 + 4, 10, 0, 7); x.fill();
      x.fillStyle = 'rgba(255,255,255,.6)'; x.beginPath(); x.arc(-3, -h / 2 + 1, 3.5, 0, 7); x.fill();
      x.restore();
      boardRects.push({ x0: cx - w / 2, y0: cy - h / 2, x1: cx + w / 2, y1: cy + h / 2, it });
    });
    boardTex.needsUpdate = true;
  }
  function fit(x, t, w) { t = String(t); while (t.length > 3 && x.measureText(t).width > w) t = t.slice(0, -2).trimEnd() + '…'; return t; }
  function setBoard(items) {
    items = (items || []).filter(i => i && i.title); const sig = JSON.stringify(items.map(i => [i.id, i.title, i.img, i.text]));
    if (!board) board = buildBoard();
    if (sig === boardSig) return; boardSig = sig; boardItems = items;
    for (const it of items) if (it.img && !boardImg.has(it.img)) {
      const im = new Image(); boardImg.set(it.img, im);
      fetch(it.img).then(r => r.ok ? r.text() : Promise.reject()).then(svg => {     // SVGs need a size before a canvas will draw them
        if (!/<svg[^>]*\swidth=/.test(svg)) svg = svg.replace('<svg', '<svg width="512" height="512"');
        if (!/xmlns=/.test(svg)) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
        im.onload = drawBoard; im.src = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
      }).catch(() => {});
    }
    drawBoard();
  }
  function boardHit(h) {   // which drawing or poem on the board the pointer is over
    if (!h?.uv) return null; const px = h.uv.x * BW, py = (1 - h.uv.y) * BH;
    return boardRects.find(b => px >= b.x0 && px <= b.x1 && py >= b.y0 && py <= b.y1)?.it || null;
  }
  const boardFront = () => board.localToWorld(new THREE.Vector3(0, 0, 2.2)).setY(0);
  let camGoal = null;

  // a little open book floats over things that have a story, so visitors know they can click them
  function keepsakeMark(o) {
    const s = textSprite('📖', 84); s.scale.set(0.55, 0.55, 1); s.renderOrder = 2; s.userData.bob = true; s.userData.noAO = true;
    const box = new THREE.Box3().setFromObject(o); s.userData.bobY = Math.min(Math.max(box.max.y, 0.8), 4.5) + 0.45; s.position.set(0, s.userData.bobY, 0);
    s.traverse(n => { n.userData.item = o.userData.item; }); o.add(s);
  }

  // ---------------------------------------------------------------- carrying things to a new spot
  // When his brain moves something, the thing doesn't slide there by itself: Gino trots over, nudges his nose under
  // it, swings it onto his back, carries it to the new spot and sets it down. Several moves wait their turn.
  const carries = []; let carry = null;
  const CLEAR = { pond: 2.3, fountain: 1.4, garden: 1.3, house: 1.6, picnic: 1.3, path: 1.2, bed: 1.2, tent: 1.5, well: 0.9, windmill: 0.9, pumpkins: 1.0, campfire: 0.9 };
  function regrass() {   // re-trample the grass round his things (waits until nothing is being carried)
    if (carry || carries.length) return;
    const gsig = state.habitat.map(i => [i.id, i.x, i.y, i.kind, i.size].join()).join(';') + (board ? ';board' : '');
    if (gsig !== grass.userData.sig) { grass.userData.sig = gsig; layGrass([...[...itemObjs.values()].map(o => [o.position.x, o.position.z, (CLEAR[o.userData.kind] || 0.65) * (o.userData.grow || o.scale.x || 1)]), ...(board ? [[BOARD_AT.x, BOARD_AT.z + 1.6, 0.6]] : [])]); }
  }
  function queueCarry(o, x, z) {
    const to = new THREE.Vector3(x, groundY(x, z), z), had = carry?.o === o ? carry : carries.find(c => c.o === o);
    if (had) { had.to.copy(to); return; }
    if (carries.length >= 6) { o.position.copy(to); return; }    // a big rearrangement: the rest just appear
    carries.push({ o, to });
  }
  function dropCarry(o, snap) {   // the thing vanished or changed shape: forget about carrying it
    for (let i = carries.length - 1; i >= 0; i--) if (carries[i].o === o) { if (snap) o.position.copy(carries[i].to); carries.splice(i, 1); }
    if (carry?.o === o) { if (snap) { o.position.copy(carry.to); o.rotation.y = carry.spin; o.scale.setScalar(carry.base); } o.userData.carried = false; carry = null; }
  }
  function solidBox(o) {   // its size without the floating book, smoke puffs and sprites
    const b = new THREE.Box3(), tb = new THREE.Box3(); o.updateWorldMatrix(true, true);
    o.traverse(n => { if (!n.isMesh || n.isSprite || n.userData.puff || !n.geometry) return; if (!n.geometry.boundingBox) n.geometry.computeBoundingBox(); b.union(tb.copy(n.geometry.boundingBox).applyMatrix4(n.matrixWorld)); });
    return b.isEmpty() ? b.setFromCenterAndSize(o.position.clone().setY(o.position.y + 0.5), v3.set(1, 1, 1)) : b;
  }
  const NOSE = 1.15;   // how far in front of his middle his nose is
  function besideIt(p, rad) {   // where to stand to reach something at p: on his side of it, nose against it
    const d = new THREE.Vector3(gino.position.x - p.x, 0, gino.position.z - p.z);
    if (d.lengthSq() < 1e-4) d.set(1, 0, 0);
    return d.normalize().multiplyScalar(rad + NOSE).add(p).setY(0);
  }
  function startCarry(c) {
    const o = c.o; carry = c;
    if (o.userData.grow) { o.scale.setScalar(o.userData.grow); o.userData.grow = 0; }
    c.from = o.position.clone(); c.spin = o.rotation.y; c.base = o.scale.x;
    const box = solidBox(o), size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3());
    c.rad = Math.min(2.6, Math.max(0.35, Math.max(size.x, size.z) / 2));
    c.k = Math.min(1, 1.25 / Math.max(size.x, size.y * 1.3, size.z, 0.01));        // big things shrink down to fit on his back
    c.h = size.y * c.k;
    c.foot = o.worldToLocal(ctr.setY(box.min.y));                               // bottom middle, in its own units
    c.phase = 'fetch'; c.t0 = 0; c.name = o.userData.item?.name || 'things';
    target.copy(besideIt(c.from, c.rad));
    R.label = ''; R.face = null; R.pond = null; R.pose = null; R.arrived = true; R.cur = R.next = 'idle'; R.aw = 0;
  }
  const backAt = new THREE.Vector3(), bob3 = new THREE.Vector3();
  function onBack(o, k, scale) {   // put o so its bottom middle sits on his back (k: 0 = where it was, 1 = on his back)
    G.body.localToWorld(backAt.set(-0.12, 1.3, 0));
    const turn = THREE.MathUtils.lerp(carry.spin, gino.rotation.y + carry.rel, k);
    o.rotation.y = turn; o.scale.setScalar(scale);
    return backAt.sub(bob3.copy(carry.foot).multiplyScalar(scale).applyAxisAngle(up, turn));
  }
  function faceTo(p, dt) {
    let diff = Math.atan2(-(p.z - gino.position.z), p.x - gino.position.x) - gino.rotation.y; diff = Math.atan2(Math.sin(diff), Math.cos(diff));
    gino.rotation.y += diff * Math.min(1, dt * 5); return Math.abs(diff);
  }
  const ease = k => k * k * (3 - 2 * k);
  function stepCarry(t, dt) {   // returns how far his head should dip (0..1)
    const c = carry, o = c.o, near = Math.hypot(target.x - gino.position.x, target.z - gino.position.z) < 0.1;
    if (c.phase === 'fetch' && near) { c.phase = 'aim'; c.t0 = t; }
    if (c.phase === 'aim' && (faceTo(c.from, dt) < 0.06 || t - c.t0 > 1.5)) { c.phase = 'lift'; c.t0 = t; c.rel = c.spin - gino.rotation.y; o.userData.carried = true; }
    if (c.phase === 'lift') {
      const k = Math.min(1, (t - c.t0) / 1.4), m = ease(Math.max(0, (k - 0.3) / 0.7));
      const at = onBack(o, m, THREE.MathUtils.lerp(c.base, c.base * c.k, m));
      o.position.lerpVectors(c.from, at, m); o.position.y += Math.sin(m * Math.PI) * 0.7 + (k < 0.3 ? Math.abs(Math.sin(k * 40)) * 0.04 : 0);
      if (k >= 1) { c.phase = 'haul'; target.copy(besideIt(c.to, c.rad)); }
      return k < 0.3 ? ease(k / 0.3) : 1 - ease(Math.min(1, (k - 0.3) / 0.5));
    }
    if (c.phase === 'haul') {
      o.position.copy(onBack(o, 1, c.base * c.k)); o.position.y += Math.sin(t * 9) * 0.015;
      if (near) { c.phase = 'aim2'; c.t0 = t; }
      return 0;
    }
    if (c.phase === 'aim2') {
      o.position.copy(onBack(o, 1, c.base * c.k));
      if (faceTo(c.to, dt) < 0.06 || t - c.t0 > 1.5) { c.phase = 'drop'; c.t0 = t; c.at = o.position.clone(); c.rel2 = o.rotation.y; }
      return 0;
    }
    if (c.phase === 'drop') {
      const k = Math.min(1, (t - c.t0) / 1.3), m = ease(Math.min(1, k / 0.75));
      o.position.lerpVectors(c.at, c.to, m); o.position.y += Math.sin(m * Math.PI) * 0.6;
      o.rotation.y = THREE.MathUtils.lerp(c.rel2, c.spin + Math.round((c.rel2 - c.spin) / 6.2832) * 6.2832, m);
      o.scale.setScalar(THREE.MathUtils.lerp(c.base * c.k, c.base, m));
      if (k >= 1) {   // set down: a happy little hop, then he stands back and looks at it
        o.position.copy(c.to); o.rotation.y = c.spin; o.scale.setScalar(c.base); o.userData.carried = false; carry = null; hop = 0.8;
        if (R.on) { R.cur = R.next = 'look'; R.pose = null; R.face = c.to.clone(); R.arrived = true; R.until = t + 7; R.aw = 0; R.label = `admiring where he put the ${c.name}`; target.copy(gino.position); }
        else target.copy(anchor);
        regrass();
      }
      return k < 0.75 ? ease(Math.min(1, k / 0.45)) : 1 - ease((k - 0.75) / 0.25);
    }
    return 0;
  }

  function update(s) {
    state = s; weather = weatherOverride || s.weather?.kind || 'clear'; env.art = s.art || [];
    const seen = new Set();
    for (const it of s.habitat) {
      seen.add(it.id);
      const sig = [it.name, it.emoji, it.kind, it.color, it.size, !!it.story].join('|');
      let o = itemObjs.get(it.id);
      if (o && o.userData.sig !== sig) { dropCarry(o, false); itemsGroup.remove(o); dispose(o); o = null; }
      if (o) o.traverse(n => { n.userData.item = it; });   // a story can change without the shape changing
      if (!o) { o = buildItem(it); o.userData.sig = sig; if (it.story) keepsakeMark(o); itemsGroup.add(o); itemObjs.set(it.id, o); o.scale.setScalar(placed ? 0.01 : Math.min(2.5, Math.max(0.4, it.size || 1))); o.userData.grow = Math.min(2.5, Math.max(0.4, it.size || 1)); }
      const x = cellX(it.x), z = cellZ(it.y), cell = it.x + ',' + it.y;
      if (o.userData.cell && o.userData.cell !== cell && placed && !s.asleep) queueCarry(o, x, z);   // he moved it: go and carry it
      else if (carry?.o === o || carries.some(c => c.o === o)) { if (o.userData.cell !== cell) queueCarry(o, x, z); }
      else o.position.set(x, groundY(x, z), z);
      o.userData.cell = cell;
    }
    for (const [id, o] of itemObjs) if (!seen.has(id)) { dropCarry(o, false); itemsGroup.remove(o); dispose(o); itemObjs.delete(id); }
    ponds = [...itemObjs.values()].filter(o => o.userData.kind === 'pond');
    regrass();
    hangArt();
    anchor.set(cellX(s.pos[0]) + 1.0, 0, cellZ(s.pos[1]) + 1.0);
    const p = ponds.find(o => Math.hypot(o.position.x - cellX(s.pos[0]), o.position.z - cellZ(s.pos[1])) < 0.1);
    if (p) anchor.set(p.position.x, 0, p.position.z);
    const sig = [s.pos, s.activity, !!s.asleep].join('|');   // his brain decided something new: go there and do it for a while
    if (carry) R.sig = sig;   // busy carrying something; he'll get back to his day afterwards
    else if (!R.on) { target.copy(anchor); R.cur = R.next = actFor(s.activity, false); R.aw = 1; }
    else if (sig !== R.sig) { R.sig = sig; goHome(placed ? 40 : 6); }
    if (!placed) { gino.position.copy(target); gino.position.y = groundY(target.x, target.z); placed = true; }
    const em = s.asleep ? '' : (EMOJI[(s.emotion || '').toLowerCase()] || '');
    if (em !== lastEmote) { lastEmote = em; const cv = G.emote.material.map.image, x = cv.getContext('2d'); x.clearRect(0, 0, 128, 128); if (em) { x.fillStyle = 'rgba(255,255,255,.92)'; x.beginPath(); x.arc(64, 64, 58, 0, 6.3); x.fill(); x.font = '72px serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(em, 64, 70); } G.emote.material.map.needsUpdate = true; G.emote.userData.pop = 1; }
  }

  // ---------------------------------------------------------------- time of day and weather
  const K = { nTop: C('#060b1e'), dTop: C('#3f8fd8'), nHor: C('#16224a'), dHor: C('#bfe3f5'), warm: C('#ff9d5c'), grey: C('#8d99a6'), sunDay: C('#fff3d6'), sunLow: C('#ffab66'), moonL: C('#8fa6ff'), hemiN: C('#5d70b5'), hemiD: C('#dff3ff'), white: C('#ffffff'), stormCloud: C('#77808c'), nightCloud: C('#2a3352') };
  const tmp = new THREE.Color(), tmp2 = new THREE.Color();
  function applySky(hour, dt) {
    const el = Math.sin((hour - 6) / 12 * Math.PI);
    const day = smooth(-0.14, 0.26, el), glow = Math.max(0, 1 - Math.abs(el) / 0.34) * (el > -0.22 ? 1 : 0);
    const want = { cloud: { clear: 0.22, cloudy: 0.85, rain: 1, snow: 0.9, fog: 0.5 }[weather] ?? 0.22, rain: weather === 'rain' ? 1 : 0, snow: weather === 'snow' ? 1 : 0, fog: weather === 'fog' ? 1 : weather === 'rain' || weather === 'snow' ? 0.45 : 0 };
    for (const k in W) W[k] += (want[k] - W[k]) * Math.min(1, dt * 0.8);
    const dull = Math.max(W.cloud - 0.3, 0) / 0.7;
    skyU.top.value.copy(K.nTop).lerp(K.dTop, day).lerp(K.grey, dull * 0.7 * day).lerp(K.warm, glow * 0.25);
    skyU.horizon.value.copy(K.nHor).lerp(K.dHor, day).lerp(K.grey, dull * 0.6 * day).lerp(K.warm, glow * 0.6 * (1 - dull * 0.7));
    scene.fog.color.copy(skyU.horizon.value); scene.fog.near = THREE.MathUtils.lerp(60, 8, W.fog); scene.fog.far = THREE.MathUtils.lerp(300, 70, W.fog);
    const az = (hour - 12) / 12 * Math.PI, sd = new THREE.Vector3(Math.sin(az) * 0.8, el, -0.45 + Math.cos(az) * 0.1).normalize();
    const lightDir = el > -0.05 ? sd : sd.clone().multiplyScalar(-1).setY(Math.max(0.35, -el));  // moonlight at night
    sun.target.position.copy(controls.target).setY(0); sun.position.copy(lightDir).multiplyScalar(80); if (sun.position.y < 14) sun.position.y = 14; sun.position.add(sun.target.position);
    skyU.sunDir.value.copy(sd); skyU.sunCol.value.copy(K.sunDay).lerp(K.warm, glow); skyU.glow.value = (1 - dull) * smooth(-0.2, 0.05, el);
    sunBall.position.copy(sd).multiplyScalar(620); sunBall.visible = dull < 0.8; moon.position.copy(sd).multiplyScalar(-600).setY(Math.max(-el, -0.2) * 520 + 60);
    sun.intensity = (0.32 + day * 2.7) * (1 - dull * 0.6); sun.color.copy(K.moonL).lerp(K.sunDay, day).lerp(K.sunLow, glow * 0.7);
    hemi.intensity = 0.42 - day * 0.24 + dull * 0.1 * day; hemi.color.copy(K.hemiN).lerp(K.hemiD, day); scene.environmentIntensity = 0.5 + day * 0.28;
    refreshEnv(U.time.value, `${Math.round(hour * 6)}|${Math.round(W.cloud * 8)}|${Math.round(W.fog * 4)}`);
    stars.material.opacity = (1 - day) * (1 - dull); moon.material.opacity = 1;
    cloudMat.color.copy(K.nightCloud).lerp(K.white, day).lerp(K.stormCloud, dull * 0.75).lerp(K.warm, glow * 0.3);
    waterMat.color.copy(tmp.set('#0f2444')).lerp(tmp2.set('#2a86b5'), day).lerp(K.grey, dull * 0.35); rip.offset.set(U.time.value * 0.012, U.time.value * 0.02);
    Grade.uniforms.warmth.value = 0.35 + glow * 0.65; if (composer) composer.passes[composer.passes.length - 1].uniforms.warmth.value = Grade.uniforms.warmth.value;
    if (bloom) bloom.strength = 0.28 + (1 - day) * 0.5;
    return day;
  }

  // ---------------------------------------------------------------- frame loop
  const timer = new THREE.Timer(); timer.connect(document);
  const v3 = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  let snapshot = null, quality = small ? 'low' : 'high', slow = 0, frames = 0;
  const furLayers = () => gino.traverse(n => { if (n.userData.shell) n.visible = quality === 'high' || n.userData.shell % 2 === 0; });   // half the fur layers on slow devices
  G.onReal = furLayers;   // the sculpted model's fur arrives a moment later
  function setQuality(q) {
    quality = q; const hi = q === 'high';
    furLayers();
    if (gtao) gtao.enabled = hi; renderer.setPixelRatio(Math.min(devicePixelRatio, hi ? 2 : 1)); grassShare = hi ? 1 : 0.45; grass.count = Math.round((grass.userData.full || 0) * grassShare);
    const sm = hi ? (opts.film ? 2048 : 4096) : 1024; sun.shadow.mapSize.set(sm, sm); sun.shadow.map?.dispose(); sun.shadow.map = null; resize(); opts.onQuality?.(q);
  }
  renderer.setAnimationLoop(() => {
    timer.update(); const raw = timer.getDelta(), dt = Math.min(raw, 0.1), t = timer.getElapsed(); U.time.value = t;
    if (quality === 'high' && opts.autoQuality !== false && intro >= 1 && ++frames > 30) { slow += raw > 0.045 ? 1 : -0.5; slow = Math.max(0, slow); if (slow > 50) setQuality('low'); }
    const now = new Date();
    const hour = timeMode === 'day' ? 12.5 : timeMode === 'sunset' ? 17.75 : timeMode === 'night' ? 23 : opts.clock ? opts.clock() : now.getHours() + now.getMinutes() / 60;
    const day = applySky(hour, dt);

    // camera: fly in once, then idle orbit / follow / focus
    if (intro < 1) { intro = Math.min(1, intro + dt / 4.5); const k = 1 - Math.pow(1 - intro, 3); camera.position.lerpVectors(v3.set(-70, 60, 95), HOME, k); if (intro >= 1) idleAt = performance.now() + 12000; }
    if (follow) controls.target.lerp(v3.set(gino.position.x, gino.position.y + 0.9, gino.position.z), Math.min(1, dt * 3));
    else if (focus) { controls.target.lerp(focus, Math.min(1, dt * 4)); if (controls.target.distanceTo(focus) < 0.05) focus = null; }
    if (camGoal) { camera.position.lerp(camGoal, Math.min(1, dt * 2.2)); if (camera.position.distanceTo(camGoal) < 0.05) camGoal = null; }
    if (performance.now() > idleAt && !follow) controls.autoRotate = true;

    // Gino
    if (!carry && carries.length && placed) {
      if (state.asleep) { for (const c of carries) c.o.position.copy(c.to); carries.length = 0; regrass(); }
      else startCarry(carries.shift());
    }
    const dip = carry ? stepCarry(t, dt) : 0, hauling = carry && (carry.phase === 'fetch' || carry.phase === 'haul');
    const asleep = state.asleep, inPond = ponds.some(o => !o.userData.carried && Math.hypot(o.position.x - gino.position.x, o.position.z - gino.position.z) < 1.3 * o.scale.x);
    if (R.on && placed && !carry) {
      if (asleep) { if (R.next !== 'sleep') { R.next = 'sleep'; R.pose = null; R.label = ''; R.face = null; R.arrived = false; target.copy(anchor); } }
      else if (R.next === 'sleep') goHome(6);
      else if (R.arrived && t > R.until && !opts.director) pickNext();   // in a clip, the director decides where he goes
      if (R.arrived && R.cur === R.next) {
        if (R.cur === 'swim' && R.pond) target.set(R.pond.position.x + Math.cos(t * 0.45) * 0.6 * R.pond.scale.x, 0, R.pond.position.z + Math.sin(t * 0.45) * 0.6 * R.pond.scale.x);
        if (R.cur === 'zoom' && Math.hypot(target.x - gino.position.x, target.z - gino.position.z) < 0.4) { const a = Math.random() * 6.283; target.set(THREE.MathUtils.clamp(R.zc.x + Math.cos(a) * 5, -16, 16), 0, THREE.MathUtils.clamp(R.zc.z + Math.sin(a) * 5, -10, 10)); }
      }
    }
    const moving = R.cur === R.next && (R.cur === 'swim' || R.cur === 'zoom') && R.arrived;
    const d = v3.subVectors(target, gino.position); d.y = 0;
    const dist = d.length(), walking = carry ? hauling && dist > 0.08 : dist > 0.08 && (!asleep || (R.on && !R.arrived)) && (R.aw < 0.25 || moving), down = asleep && !walking && !carry;
    const speed = carry ? (carry.phase === 'haul' ? 1.7 : dist > 8 ? 4.4 : 2.3) : inPond ? 1.1 : moving && R.cur === 'zoom' ? 6.5 : dist > 8 ? 4.4 : 2.3, run = speed > 4;
    if (walking) {
      const step = Math.min(dist, speed * dt); d.normalize(); gino.position.addScaledVector(d, step);
      let diff = Math.atan2(-d.z, d.x) - gino.rotation.y; diff = Math.atan2(Math.sin(diff), Math.cos(diff)); gino.rotation.y += diff * Math.min(1, dt * (run ? 12 : 8));
    } else if (R.face && R.arrived && !asleep && R.cur !== 'hops') {
      let diff = Math.atan2(-(R.face.z - gino.position.z), R.face.x - gino.position.x) - gino.rotation.y; diff = Math.atan2(Math.sin(diff), Math.cos(diff)); gino.rotation.y += diff * Math.min(1, dt * 4);
    }
    if (!R.arrived && dist <= 0.08 && !carry) { R.arrived = true; R.until = t + R.hold; if (R.next === 'zoom') R.zc = gino.position.clone(); }
    if (R.cur !== R.next || !R.arrived) { R.aw = Math.max(0, R.aw - dt * 3.5); if (R.aw < 0.02 && R.arrived) R.cur = R.next; }
    else if (!walking || moving) R.aw = Math.min(1, R.aw + dt * 2.2);
    const c = R.cur, a = asleep ? 0 : R.aw * R.aw * (3 - 2 * R.aw);
    if (c === 'hops' && a > 0.6) { if (hop <= 0.02) hop = 1; gino.rotation.y += dt * 2.2; }
    const posing = R.pose && R.arrived && c === R.next && !walking && !carry ? a : 0;
    if (R.pose?.hearts && posing > 0.6 && t - heartT > 2.4) { hop = 1; heartT = t; }   // a happy hop, hearts and all
    hop = Math.max(0, hop - dt * 1.6);
    const gy = groundY(gino.position.x, gino.position.z) + (inPond ? -0.46 : 0);
    gino.position.y += (gy - gino.position.y) * Math.min(1, dt * 6);
    const sleepK = G.sleepK = THREE.MathUtils.lerp(G.sleepK ?? 0, down ? 1 : 0, Math.min(1, dt * 3));
    const lie = Math.max(sleepK, c === 'nap' ? a : 0), rollX = c === 'roll' ? Math.PI * a : 0;   // on his back, paws in the air
    const bRz = { sit: 0.36, stretch: -0.24 }[c] || 0, rear = c === 'sit' ? 0.45 : 1;
    const bRx = c === 'scratch' ? Math.sin(t * 6) * 0.11 : c === 'dance' ? Math.sin(t * 3) * 0.13 : c === 'roll' ? Math.sin(t * 5) * 0.32 : 0;
    const gait = run ? 15 : 9;
    G.body.position.y = -0.3 * lie + (walking ? Math.abs(Math.sin(t * gait)) * (run ? 0.11 : 0.05) : Math.sin(t * 1.6) * 0.012) + Math.abs(Math.sin(hop * Math.PI * 2)) * 0.5 * hop + (inPond ? Math.sin(t * 1.3) * 0.03 : 0)
      + 0.63 * (1 - Math.cos(rollX)) + (c === 'dance' ? Math.abs(Math.sin(t * 6)) * 0.14 * a : 0) + (c === 'sit' ? 0.03 * a : 0);
    G.body.position.z = c === 'scratch' ? Math.sin(t * 6) * 0.05 * a : 0;
    G.body.rotation.x = rollX + bRx * a + (inPond ? Math.sin(t * 0.9) * 0.04 : 0);
    G.body.rotation.z = bRz * a + (run && walking ? Math.sin(t * gait) * 0.05 : 0) - dip * 0.14 + (carry?.phase === 'haul' ? 0.035 : 0);   // nose down to scoop things up
    G.body.scale.set(1, 1 + Math.sin(t * (lie > 0.5 ? 1.1 : 1.8)) * 0.022, 1);
    const paws = c === 'roll' ? 0.5 : c === 'dance' ? 0.3 : c === 'swim' ? 0.4 : 0;
    G.legs.forEach((l, i) => { l.rotation.z = walking ? Math.sin(t * gait + (i % 3 ? Math.PI : 0)) * (run ? 0.85 : inPond ? 0.4 : 0.6) : Math.sin(t * 7 + i * 1.7) * paws * a; l.scale.y = (1 - 0.75 * lie) * (i > 1 ? 1 + (rear - 1) * a : 1); });
    const hZ = { graze: -0.4 + Math.sin(t * 7) * 0.12, sniff: -0.3 + Math.sin(t * 11) * 0.04, sit: -0.28, stretch: 0.4, scratch: 0.18, look: 0.26, dance: Math.sin(t * 6) * 0.16, roll: 0.2 }[c] || 0;
    const hY = c === 'look' ? Math.sin(t * 0.8) * 0.6 : c === 'sniff' ? Math.sin(t * 1.3) * 0.25 : c === 'graze' || c === 'roll' ? 0 : Math.sin(t * 0.4) * 0.35;
    G.head.rotation.z = -0.35 * lie + hZ * a + Math.sin(t * 0.7) * 0.05 * (1 - a) + hop * 0.3 - dip * 0.55 + (carry?.phase === 'haul' ? 0.12 : 0);
    G.head.rotation.y = down || walking ? 0 : hY;
    const blink = down || lie > 0.6 || (c === 'roll' && a > 0.5) || (t % 4.2) < 0.13 || hop > 0.2; G.eyes.forEach(e => e.scale.y = blink ? 0.018 : 0.105);
    G.ears.forEach((e, i) => e.rotation.x = (Math.sin(t * 2.3 + i) > 0.96 ? 0.5 : 0));
    G.orange.visible = (inPond && (!walking || moving)) || (!!R.pose?.orange && posing > 0.4);
    G.zs.forEach((z, i) => { const k = (t * 0.35 + i / 3) % 1; z.visible = down || (c === 'nap' && a > 0.7); z.position.set(1.0 + k * 0.5, 1.5 + k * 1.3, 0); z.scale.setScalar(0.25 + k * 0.4); z.material.opacity = 1 - k; });
    G.hearts.forEach((h, i) => { const k = (t - heartT) / 1.6 - i * 0.08; h.visible = k > 0 && k < 1; if (h.visible) { h.position.set(Math.cos(i * 1.05) * (0.3 + k * 0.7), 1.6 + k * 1.6, Math.sin(i * 1.05) * (0.3 + k * 0.7)); h.scale.setScalar(0.3 + Math.sin(k * Math.PI) * 0.25); h.material.opacity = 1 - k * k; } });
    G.sync?.();   // copy the moves above onto the sculpted model's skeleton
    const ep = G.emote.userData.pop = Math.max(0, (G.emote.userData.pop || 0) - dt * 1.5);
    G.emote.visible = !!lastEmote; G.emote.position.y = 2.15 + Math.sin(t * 1.5) * 0.05 - 0.3 * sleepK + (carry?.o.userData.carried ? carry.h + 0.15 : 0); G.emote.scale.setScalar(0.6 + Math.sin(ep * Math.PI) * 0.35);

    // living details on built things
    itemsGroup.traverse(nd => {
      const u = nd.userData;
      if (u.flame) { nd.scale.y = u.flame * (0.9 + Math.sin(t * 13 + u.flame * 9) * 0.14 + Math.sin(t * 7.3) * 0.08); nd.rotation.y = t * 2; }
      else if (u.bob) nd.position.y = (u.bobY ?? 1.05) + Math.sin(t * 1.4 + nd.id) * 0.08;
      else if (u.spin) nd.rotation.z = t * u.spin;
      else if (u.swing) nd.rotation[u.axis || 'x'] = Math.sin(t * 1.3 + nd.id) * u.swing;
      else if (u.wobble !== undefined) nd.rotation.z = Math.sin(t * 1.6 + u.wobble) * 0.09;
      else if (u.nightGlow) nd.material.emissiveIntensity = u.nightGlow * (1 - day);
      else if (u.puff) { const p = u.puff, k = (t * p.speed + p.i) % 1, a = p.i * 40; nd.position.set(p.at[0] + Math.cos(a) * p.spread * k, p.at[1] + (p.arc ? Math.sin(k * Math.PI) * p.rise : k * p.rise), p.at[2] + Math.sin(a) * p.spread * k); nd.scale.setScalar(p.size * (p.arc ? 1 : 0.5 + k)); nd.material.opacity = (1 - k) * 0.85; }
      if (nd.isPointLight) nd.intensity = (u.nightLight * (1 - day) + (u.flicker ? 4 : 0)) * (u.flicker ? 0.85 + Math.sin(t * 17) * 0.1 + Math.sin(t * 5.3) * 0.06 : 1);
    });
    for (const o of itemObjs.values()) if (o.userData.grow) { const s = o.scale.x + (o.userData.grow * 1.0 - o.scale.x) * Math.min(1, dt * 5); o.scale.setScalar(s); if (Math.abs(o.userData.grow - s) < 0.002) { o.scale.setScalar(o.userData.grow); o.userData.grow = 0; } }
    boat.position.y = WATER_Y - 0.12 + Math.sin(t * 1.1) * 0.05; boat.rotation.z = Math.sin(t * 0.8) * 0.04; boat.rotation.x = Math.sin(t * 0.6) * 0.03;

    // sky life
    const visClouds = Math.round(5 + W.cloud * 17);
    clouds.forEach((cl, i) => { cl.position.x += dt * (0.8 + W.rain * 1.5); if (cl.position.x > 200) cl.position.x = -200; cl.visible = i < visClouds; });
    cloudMat.opacity = 0.35 + day * 0.6;
    const calm = day > 0.5 && W.rain < 0.3 && W.snow < 0.3;
    birds.forEach(b => { const u = b.userData; u.a += dt * u.s; b.visible = calm; b.position.set(u.cx + Math.cos(u.a) * u.r, u.h + Math.sin(u.a * 2) * 1.5, u.cz + Math.sin(u.a) * u.r); b.rotation.y = -u.a - Math.PI / 2; u.wings.forEach((w, i) => w.rotation.x = (i ? -1 : 1) * Math.sin(t * 7 + u.r) * 0.6); });
    const bugs = env.season !== 'winter' && W.rain < 0.3;
    flies.forEach(f => { const u = f.userData; u.a += dt * u.s; const x = Math.cos(u.a) * u.r, z = Math.sin(u.a * 1.3) * u.r * 0.7; f.visible = bugs; f.position.set(x, groundY(x, z) + u.h + Math.sin(t * 2 + u.r) * 0.3, z); f.rotation.y = -u.a;
      const isDay = day > 0.5; u.m.color.copy(isDay ? u.c : tmp.set('#f6ff9a').multiplyScalar(3)); u.m.opacity = isDay ? 0.95 : 0.35 + Math.abs(Math.sin(t * 2 + u.r)) * 0.65;
      u.dot.visible = !isDay; u.wings.forEach((w, i) => { w.visible = isDay; w.rotation.z = (i ? -1 : 1) * (0.2 + Math.abs(Math.sin(t * 11 + u.r)) * 1.1); }); });

    // precipitation follows the camera target
    const cx = controls.target.x, cz = controls.target.z;
    rain.visible = W.rain > 0.02; rain.material.opacity = W.rain * 0.55;
    if (rain.visible) { for (let i = 0; i < RN; i++) { const y = 40 - ((rainSeed[i * 3 + 1] + t * 34) % 40), x = cx + rainSeed[i * 3], z = cz + rainSeed[i * 3 + 2]; rainPos.set([x, y, z, x + 0.12, y + 0.9, z], i * 6); } rainGeo.attributes.position.needsUpdate = true; }
    const leafy = !!S.leaves && W.rain < 0.3, fl = Math.max(W.snow, leafy ? 0.5 : 0);
    flakes.visible = fl > 0.02; flakes.material.opacity = Math.min(1, fl * 1.2);
    if (flakes.visible) { const snow = W.snow > 0.3; flakes.material.color.set(snow ? '#ffffff' : '#e08a2e'); flakes.material.size = snow ? 0.22 : 0.3; const cnt = snow ? FN : 140;
      for (let i = 0; i < FN; i++) { const s = flakeSeed[i * 4 + 3]; const y = i < cnt ? 30 - ((flakeSeed[i * 4 + 1] + t * (snow ? 2.6 : 1.5)) % 30) : -50; flakePos.set([cx + flakeSeed[i * 4] + Math.sin(t * 0.8 + s) * 1.5, y, cz + flakeSeed[i * 4 + 2] + Math.cos(t * 0.6 + s) * 1.5], i * 3); } flakeGeo.attributes.position.needsUpdate = true; }

    opts.director?.(t, dt);   // the clip maker (static/clip.html) steers the camera itself, shot by shot
    controls.update();
    sky.position.copy(camera.position);
    if (composer) composer.render(); else renderer.render(scene, camera);
    if (snapshot) { const cb = snapshot; snapshot = null; renderer.domElement.toBlob(cb, 'image/png'); }
  });

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h; camera.fov = w / h < 0.9 ? 58 : 42; camera.updateProjectionMatrix();
    renderer.setSize(w, h); composer?.setPixelRatio(renderer.getPixelRatio()); composer?.setSize(w, h);
  }
  new ResizeObserver(resize).observe(container); resize(); if (small) setQuality('low');

  // ---------------------------------------------------------------- pointer: hover names, pet Gino, double-click to look at something
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2(); let hoverT = 0, downAt = null;
  function hit(ev) {
    const r = renderer.domElement.getBoundingClientRect();
    ptr.set((ev.clientX - r.left) / r.width * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, camera);
    const gh = ray.intersectObject(gino, true).find(h => !h.object.isSprite), ih = ray.intersectObjects(itemsGroup.children, true)[0];
    if (gh && (!ih || gh.distance < ih.distance)) return { gino: true, r };
    const bh = board && ray.intersectObject(board, true)[0];
    if (bh && (!ih || bh.distance < ih.distance)) return { board: true, piece: bh.object === boardFace ? boardHit(bh) : null, r };
    return { item: ih?.object.userData.item, obj: ih?.object, r };
  }
  const doing = () => carry ? (carry.phase === 'fetch' || carry.phase === 'aim' ? `going to pick up the ${carry.name}` : carry.phase === 'lift' ? `lifting the ${carry.name}` : carry.phase === 'drop' ? `setting down the ${carry.name}` : `carrying the ${carry.name} to its new spot`)
    : state.asleep ? 'sleeping' : R.on && R.label ? (R.arrived ? R.label : 'trotting off somewhere') : state.activity;
  const el = renderer.domElement;
  // Mac trackpads in Safari: a pinch sends its own gesture events and zooms the whole page (or flips to the tab
  // overview) unless we take it. Turn the pinch into camera zoom instead. Other browsers send it as ctrl+wheel,
  // which OrbitControls already handles.
  let pinch = 1;
  const pv = new THREE.Vector3(), dolly = k => { const off = pv.copy(camera.position).sub(controls.target), d = THREE.MathUtils.clamp(off.length() * k, controls.minDistance, controls.maxDistance); camera.position.copy(controls.target).add(off.setLength(d)); };
  el.addEventListener('gesturestart', ev => { ev.preventDefault(); pinch = ev.scale || 1; });
  el.addEventListener('gesturechange', ev => { ev.preventDefault(); const sc = ev.scale || 1; if (pinch > 0 && sc > 0) dolly(pinch / sc); pinch = sc; });
  el.addEventListener('gestureend', ev => ev.preventDefault());
  el.addEventListener('pointermove', ev => {
    const nw = performance.now(); if (nw - hoverT < 60) return; hoverT = nw;
    const h = hit(ev); let text = '';
    if (h.gino) text = 'Gino' + (doing() ? ' · ' + doing() : '') + (opts.petHint ?? ' (click to pet)');
    else if (h.piece) text = `${h.piece.kind === 'dream' ? '🌙' : h.piece.img ? '🎨' : '📝'} “${h.piece.title}”, ${h.piece.kind === 'dream' ? 'a painting of a dream' : h.piece.img ? 'a drawing' : 'a ' + h.piece.kind} by Gino · click to ${h.piece.img ? 'look' : 'read'}`;
    else if (h.board) text = "📌 Gino's creations board";
    else if (h.item) text = `${h.item.emoji || ''} ${h.item.name}${h.item.description ? ' — ' + h.item.description : ''}${h.item.story && opts.onItem ? ' · 📖 click for its story' : ''}`;
    tooltip.textContent = text; tooltip.style.display = text ? 'block' : 'none'; el.style.cursor = h.gino || h.piece || (h.item?.story && opts.onItem) ? 'pointer' : 'grab';
    tooltip.style.left = Math.min(h.r.width - 240, Math.max(8, ev.clientX - h.r.left + 14)) + 'px'; tooltip.style.top = (ev.clientY - h.r.top + 14) + 'px';
  });
  el.addEventListener('pointerleave', () => { tooltip.style.display = 'none'; });
  el.addEventListener('pointerdown', ev => { downAt = [ev.clientX, ev.clientY]; });
  el.addEventListener('pointerup', ev => {
    if (!downAt || Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 6) return;
    const h = hit(ev);
    if (h.gino) { hop = 1; heartT = timer.getElapsed(); opts.onPet?.(); }
    else if (h.piece) opts.onPiece?.(h.piece);
    else if (h.item?.story) opts.onItem?.(h.item);
  });
  el.addEventListener('dblclick', ev => { const h = hit(ev); if (h.gino) return; if (h.board) { api.showBoard(); return; } if (h.item) { const o = itemObjs.get(h.item.id); if (o) { focus = o.position.clone().setY(o.position.y + 1); follow = false; opts.onFollow?.(false); } } });

  const api = {
    update,
    setBoard,
    showBoard() {   // walk the camera up to the board so its pieces can be read
      if (!board) return; follow = false; opts.onFollow?.(false); controls.autoRotate = false; idleAt = performance.now() + 40000; intro = 1;
      focus = board.localToWorld(new THREE.Vector3(0, 2.1, 0)); camGoal = board.localToWorld(new THREE.Vector3(0.8, 2.8, 8.4));
    },
    lookAt(gx, gy) {   // point the camera at a spot of his home, in grid squares
      const x = cellX(gx), z = cellZ(gy); follow = false; opts.onFollow?.(false); controls.autoRotate = false; idleAt = performance.now() + 40000; intro = 1;
      focus = new THREE.Vector3(x, groundY(x, z) + 0.8, z); camGoal = null;
    },
    get boardAt() { return [BOARD_AT.x / CELL + (GW - 1) / 2, BOARD_AT.z / CELL + (GH - 1) / 2]; },
    setFollow(v) { follow = v; focus = null; controls.autoRotate = false; idleAt = v ? Infinity : performance.now() + 25000; if (!v) focus = new THREE.Vector3(0, 0.6, 0); },
    setTime(m) { timeMode = m; },
    setQuality, get quality() { return quality; },
    setWeather(w) { weatherOverride = w; weather = w || state.weather?.kind || 'clear'; },
    photo() { return new Promise(res => { snapshot = res; }); },
    get doing() { return doing(); },
    get where() { return [gino.position.x / CELL + (GW - 1) / 2, gino.position.z / CELL + (GH - 1) / 2]; },   // where he is right now, in grid squares
    pet() { hop = 1; heartT = timer.getElapsed(); },
    _debug: { scene, camera, controls, gino, roam: R, get carry() { return carry && carry.phase; }, get queued() { return carries.length; }, cellPos: (gx, gy) => new THREE.Vector3(cellX(gx), groundY(cellX(gx), cellZ(gy)), cellZ(gy)), skip() { intro = 1; camera.position.copy(HOME); },
      snap() { target.copy(anchor); gino.position.set(target.x, groundY(target.x, target.z), target.z); R.arrived = true; },
      // the clip maker directs Gino a little: where he stands, where he walks, what he does once he's there
      place(x, z, turn) { target.set(x, 0, z); gino.position.set(x, groundY(x, z), z); if (turn !== undefined) gino.rotation.y = turn; R.arrived = true; R.until = Infinity; },
      walkTo(x, z, act = 'look', face = null) { target.set(x, 0, z); R.next = act; R.label = ''; R.hold = 1e6; R.arrived = false; R.pond = null; R.face = face ? new THREE.Vector3(face.x, 0, face.z) : null; },
      pose(act = 'idle', face = null) { target.copy(gino.position).setY(0); R.next = act; R.label = ''; R.arrived = true; R.until = Infinity; R.pond = null; R.face = face ? new THREE.Vector3(face.x, 0, face.z) : null; },
      cutePose(name) { strikePose(POSES[name] || poseFor(state.emotion)); R.arrived = true; R.until = Infinity; },
      itemPos: id => itemObjs.get(id)?.position.clone() || null,
      items: itemsGroup,
      face: (out = new THREE.Vector3()) => G.faceAt ? G.faceAt(out) : G.head.localToWorld(out.set(0.16, 0.08, 0)) },   // the middle of his face
  };
  return api;
}
