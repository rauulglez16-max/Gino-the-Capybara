// Sounds for Gino's live page: nature that follows his day and weather, plus a lofi music mix.
// The nature sounds are synthesised in the browser with Web Audio. The music is a real recording
// (static/music/lofi.m4a, about 56 minutes, chosen by Raul) that streams in bit by bit, so phones only download
// what they actually hear. It starts at a random place each visit and loops.
// Nothing plays until the visitor turns sound on (browsers block autoplay anyway).

const rand = (a, b) => a + Math.random() * (b - a);
const smooth = (a, b, v) => { const t = Math.min(1, Math.max(0, (v - a) / (b - a))); return t * t * (3 - 2 * t); };

const MUSIC_URL = '/static/music/lofi.m4a';
const MUSIC_LEVEL = 0.25;   // the recording is mastered loud; this sits it under the nature sounds like the old loop

export function createSound() {
  let ctx = null, master, musicBus, natureBus, nodes = {}, timer = null, track = null;
  let on = false, musicOn = true, natureOn = true, volume = 0.6;
  let world = { hour: 12, weather: 'clear', asleep: false };
  let nextBird = 0, nextCricket = 0, nextDrop = 0;

  function noiseBuffer(kind, seconds = 4) {
    const len = ctx.sampleRate * seconds, buf = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch); let last = 0;
      for (let i = 0; i < len; i++) {
        const w = Math.random() * 2 - 1;
        if (kind === 'brown') { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; }
        else d[i] = w;
      }
    }
    return buf;
  }
  function loop(buf, ...chain) {
    const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
    let n = src; for (const c of chain) { n.connect(c); n = c; } src.start(ctx.currentTime + Math.random()); return n;
  }
  function filt(type, f, q = 0.7) { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; }
  const gain = v => { const g = ctx.createGain(); g.gain.value = v; return g; };
  function lfo(freq, depth, target, type = 'sine') {
    const o = ctx.createOscillator(); o.type = type; o.frequency.value = freq; const g = gain(depth); o.connect(g); g.connect(target); o.start(); return o;
  }

  function build() {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = gain(0); master.connect(ctx.destination);
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -18; comp.ratio.value = 3; const lift = gain(2.6); comp.connect(lift); lift.connect(master);
    natureBus = gain(1); natureBus.connect(comp);
    musicBus = gain(0); musicBus.connect(comp);
    // the lofi mix: an <audio> element that streams the file, played through Web Audio so the volume,
    // the sound-off fade and the quieter music while he sleeps all work as before
    track = new Audio(); track.preload = 'none'; track.loop = true; track.src = MUSIC_URL;
    track.addEventListener('loadedmetadata', () => {
      if (isFinite(track.duration) && track.duration > 60) track.currentTime = rand(0, track.duration - 30);
    }, { once: true });
    const level = gain(MUSIC_LEVEL); ctx.createMediaElementSource(track).connect(level); level.connect(musicBus);

    const white = noiseBuffer('white'), brown = noiseBuffer('brown');
    // lake water: low rumble that swells and settles like little waves
    nodes.water = gain(0); loop(brown, filt('lowpass', 420), nodes.water).connect(natureBus); lfo(0.13, 0.06, nodes.water.gain);
    // breeze
    nodes.windF = filt('bandpass', 500, 0.6); nodes.wind = gain(0); loop(brown, nodes.windF, nodes.wind).connect(natureBus); lfo(0.05, 260, nodes.windF.frequency);
    // rain: hiss plus a softer body
    nodes.rain = gain(0); loop(white, filt('highpass', 900), filt('lowpass', 7000), nodes.rain).connect(natureBus);
    nodes.rainBody = gain(0); loop(brown, filt('lowpass', 900), nodes.rainBody).connect(natureBus);
  }

  // ---------------------------------------------------------------- nature events
  function chirp(t, pan) {
    const p = ctx.createStereoPanner(); p.pan.value = pan; p.connect(natureBus);
    const base = rand(2400, 4200), n = Math.floor(rand(2, 7)), gap = rand(0.07, 0.16), up = Math.random() < 0.5;
    for (let i = 0; i < n; i++) {
      const s = t + i * gap, d = rand(0.05, 0.11), o = ctx.createOscillator(), g = gain(0);
      o.frequency.setValueAtTime(base * (up ? 0.8 : 1.25), s); o.frequency.exponentialRampToValueAtTime(base * (up ? 1.3 : 0.75), s + d);
      g.gain.setValueAtTime(0, s); g.gain.linearRampToValueAtTime(0.07, s + 0.012); g.gain.exponentialRampToValueAtTime(0.0005, s + d);
      o.connect(g); g.connect(p); o.start(s); o.stop(s + d + 0.02);
    }
  }
  function cricket(t, pan, f) {
    const p = ctx.createStereoPanner(); p.pan.value = pan; p.connect(natureBus);
    const o = ctx.createOscillator(), g = gain(0); o.frequency.value = f; o.connect(g); g.connect(p);
    const pulses = Math.floor(rand(3, 5));
    for (let i = 0; i < pulses; i++) { const s = t + i * 0.045; g.gain.setValueAtTime(0, s); g.gain.linearRampToValueAtTime(0.022, s + 0.008); g.gain.linearRampToValueAtTime(0, s + 0.032); }
    o.start(t); o.stop(t + pulses * 0.045 + 0.05);
  }
  function drop(t) {
    const o = ctx.createOscillator(), g = gain(0), p = ctx.createStereoPanner(); p.pan.value = rand(-0.8, 0.8);
    o.frequency.setValueAtTime(rand(1800, 3800), t); o.frequency.exponentialRampToValueAtTime(rand(700, 1200), t + 0.05);
    g.gain.setValueAtTime(0.03, t); g.gain.exponentialRampToValueAtTime(0.0005, t + 0.06);
    o.connect(g); g.connect(p); p.connect(natureBus); o.start(t); o.stop(t + 0.08);
  }

  // ---------------------------------------------------------------- lofi
  // The music only downloads and plays while someone is listening to it.
  function playTrack() {
    if (!track) return;
    if (on && musicOn) { if (track.paused) track.play().catch(e => console.warn('music could not start', e)); }
    else if (!track.paused) track.pause();
  }

  // ---------------------------------------------------------------- mixing and scheduling
  function mix() {
    if (!ctx) return;
    const h = world.hour, t = ctx.currentTime;
    const day = smooth(5, 7, h) * (1 - smooth(19.5, 21, h));
    const wet = world.weather === 'rain' ? 1 : 0, snow = world.weather === 'snow' ? 1 : 0, grey = ['cloudy', 'fog', 'snow'].includes(world.weather) ? 1 : 0;
    const nat = natureOn ? 1 : 0;
    nodes.water.gain.setTargetAtTime(0.18 * nat * (1 - snow * 0.6), t, 1.5);
    nodes.wind.gain.setTargetAtTime((0.05 + grey * 0.06 + snow * 0.05) * nat, t, 2);
    nodes.rain.gain.setTargetAtTime(0.06 * wet * nat, t, 2); nodes.rainBody.gain.setTargetAtTime(0.12 * wet * nat, t, 2);
    musicBus.gain.setTargetAtTime(musicOn ? (world.asleep ? 0.55 : 0.8) : 0, t, 0.8);
    master.gain.setTargetAtTime(on ? volume * volume : 0, t, 0.4);
    return { day, wet, snow };
  }
  function tick() {
    const m = mix(), now = ctx.currentTime;
    if (!natureOn) return;
    const birdy = m.day * (1 - m.wet) * (1 - m.snow) * (1 + smooth(5, 6.5, world.hour) * (1 - smooth(7.5, 9, world.hour)) * 2);
    if (now >= nextBird) { if (Math.random() < birdy) chirp(now + rand(0.05, 0.4), rand(-0.9, 0.9)); nextBird = now + rand(0.8, 3.5) / Math.max(0.4, birdy); }
    const crickety = (1 - m.day) * (1 - m.wet * 0.7) * (1 - m.snow);
    if (now >= nextCricket && crickety > 0.05) { cricket(now + 0.1, -0.5, 4400); if (Math.random() < 0.7) cricket(now + rand(0.3, 0.5), 0.55, 4950); nextCricket = now + rand(0.6, 1.1) / crickety; }
    if (m.wet && now >= nextDrop) { drop(now + rand(0, 0.2)); nextDrop = now + rand(0.05, 0.35); }
  }

  return {
    get on() { return on; }, get musicOn() { return musicOn; }, get natureOn() { return natureOn; }, get volume() { return volume; },
    async setOn(v) {
      on = v;
      if (v && !ctx) { build(); timer = setInterval(tick, 200); }
      if (!ctx) return;
      if (v) { playTrack(); await ctx.resume(); }   // start the music before any wait, while the click still counts
      mix();
      if (!v) setTimeout(() => { if (!on) { ctx.suspend(); playTrack(); } }, 600);
    },
    setVolume(v) { volume = Math.min(1, Math.max(0, v)); mix(); },
    setMusic(v) { musicOn = v; mix(); if (on) setTimeout(playTrack, v ? 0 : 900); },
    setNature(v) { natureOn = v; mix(); },
    update(s) { world = { ...world, ...s }; mix(); },
    pause(v) {
      if (!ctx || !on) return;
      if (v) { ctx.suspend(); track?.pause(); } else { ctx.resume(); playTrack(); }
    },
    _debug: { get ctx() { return ctx; }, get master() { return master; }, get track() { return track; } },
  };
}
