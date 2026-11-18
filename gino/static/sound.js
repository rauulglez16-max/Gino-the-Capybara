// Sounds for Gino's live page: nature that follows his day and weather, plus a soft lofi loop.
// Everything is synthesised in the browser with Web Audio, so there are no audio files and no licences to worry about.
// Nothing plays until the visitor turns sound on (browsers block autoplay anyway).

const rand = (a, b) => a + Math.random() * (b - a);
const pick = a => a[Math.floor(Math.random() * a.length)];
const midi = n => 440 * Math.pow(2, (n - 69) / 12);
const smooth = (a, b, v) => { const t = Math.min(1, Math.max(0, (v - a) / (b - a))); return t * t * (3 - 2 * t); };

// four-bar progressions, chords as MIDI notes (all in C major / A minor, the lofi comfort zone)
const PROGRESSIONS = [
  [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]],   // Fmaj7 Em7 Dm7 Cmaj7
  [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 65]],   // Am7 Fmaj7 Cmaj7 G7
  [[50, 53, 57, 60], [55, 59, 62, 65], [48, 52, 55, 59], [57, 60, 64, 67]],   // Dm7 G7 Cmaj7 Am7
];
const MELODY = [67, 69, 72, 74, 76, 79, 81];
const BPM = 72, STEP = 60 / BPM / 4, SWING = 0.18;

export function createSound() {
  let ctx = null, master, musicBus, natureBus, nodes = {}, timer = null;
  let on = false, musicOn = true, natureOn = true, volume = 0.6;
  let world = { hour: 12, weather: 'clear', asleep: false };
  let step = 0, nextAt = 0, bar = 0, prog = PROGRESSIONS[0], nextBird = 0, nextCricket = 0, nextDrop = 0;

  function noiseBuffer(kind, seconds = 4) {
    const len = ctx.sampleRate * seconds, buf = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch); let last = 0;
      for (let i = 0; i < len; i++) {
        const w = Math.random() * 2 - 1;
        if (kind === 'brown') { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; }
        else if (kind === 'crackle') d[i] = Math.random() < 0.0006 ? (Math.random() * 2 - 1) * 0.9 : w * 0.015;
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
    musicBus = gain(0); const warm = filt('lowpass', 2400); musicBus.connect(warm); warm.connect(comp);
    // tape wobble: a slow drift in pitch shared by every note
    nodes.wob = ctx.createOscillator(); nodes.wob.frequency.value = 0.35; nodes.wobGain = gain(7); nodes.wob.connect(nodes.wobGain); nodes.wob.start();

    const white = noiseBuffer('white'), brown = noiseBuffer('brown'); nodes.brownBuf = brown;
    // lake water: low rumble that swells and settles like little waves
    nodes.water = gain(0); loop(brown, filt('lowpass', 420), nodes.water).connect(natureBus); lfo(0.13, 0.06, nodes.water.gain);
    // breeze
    nodes.windF = filt('bandpass', 500, 0.6); nodes.wind = gain(0); loop(brown, nodes.windF, nodes.wind).connect(natureBus); lfo(0.05, 260, nodes.windF.frequency);
    // rain: hiss plus a softer body
    nodes.rain = gain(0); loop(white, filt('highpass', 900), filt('lowpass', 7000), nodes.rain).connect(natureBus);
    nodes.rainBody = gain(0); loop(brown, filt('lowpass', 900), nodes.rainBody).connect(natureBus);
    // record crackle under the music
    nodes.crackle = gain(0); loop(noiseBuffer('crackle'), filt('highpass', 1500), nodes.crackle).connect(musicBus);
    nextAt = ctx.currentTime + 0.1;
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
  function keys(t, notes, vel, len) {
    notes.forEach((n, i) => {
      const s = t + i * 0.025, g = gain(0), lp = filt('lowpass', 1500 + vel * 900);
      for (const [type, det, lvl] of [['triangle', -5, 0.6], ['sine', 5, 0.5], ['sine', 1200, 0.06]]) {
        const o = ctx.createOscillator(); o.type = type; o.frequency.value = midi(n); o.detune.value = det; nodes.wobGain.connect(o.detune);
        const og = gain(lvl); o.connect(og); og.connect(lp); o.start(s); o.stop(s + len + 1.2);
        o.onended = () => { try { nodes.wobGain.disconnect(o.detune); } catch {} };
      }
      g.gain.setValueAtTime(0, s); g.gain.linearRampToValueAtTime(0.05 * vel, s + 0.015);
      g.gain.setTargetAtTime(0.02 * vel, s + 0.02, 0.5); g.gain.setTargetAtTime(0, s + len, 0.3);
      lp.connect(g); g.connect(musicBus);
    });
  }
  function bass(t, n, len) {
    const o = ctx.createOscillator(), g = gain(0); o.frequency.value = midi(n);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.16, t + 0.02); g.gain.setTargetAtTime(0.08, t + 0.05, 0.3); g.gain.setTargetAtTime(0, t + len, 0.08);
    o.connect(g); g.connect(musicBus); o.start(t); o.stop(t + len + 0.5);
  }
  function kick(t) {
    const o = ctx.createOscillator(), g = gain(0); o.frequency.setValueAtTime(110, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.12);
    g.gain.setValueAtTime(0.35, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.35); o.connect(g); g.connect(musicBus); o.start(t); o.stop(t + 0.4);
  }
  function hit(t, kind) {
    const src = ctx.createBufferSource(); src.buffer = nodes.hitBuf || (nodes.hitBuf = noiseBuffer('white', 1));
    const f = kind === 'snare' ? filt('bandpass', 1800, 0.8) : filt('highpass', 7000), g = gain(0);
    const lvl = kind === 'snare' ? 0.12 : rand(0.025, 0.04), dur = kind === 'snare' ? 0.18 : 0.04;
    g.gain.setValueAtTime(lvl, t); g.gain.exponentialRampToValueAtTime(0.0008, t + dur);
    src.connect(f); f.connect(g); g.connect(musicBus); src.start(t, rand(0, 0.5)); src.stop(t + dur + 0.02);
  }
  function playStep(t) {
    const s = step % 16, chord = prog[bar % 4];
    if (s === 0) { keys(t, chord.map(n => n + 12 * (n < 55)), 1, STEP * 7); bass(t, chord[0] - 12, STEP * 6); }
    if (s === 10) keys(t, chord.slice(1).map(n => n + 12 * (n < 55)), 0.6, STEP * 5);
    if (s === 11) bass(t, chord[0] - 12, STEP * 4);
    if (!world.asleep) {
      if (s === 0 || s === 7 || (s === 10 && Math.random() < 0.5)) kick(t);
      if (s === 4 || s === 12) hit(t, 'snare');
      if (s % 2 === 0 || Math.random() < 0.15) hit(t, 'hat');
    }
    if (s % 2 === 0 && Math.random() < 0.16) keys(t, [pick(MELODY)], 0.55, STEP * rand(2, 4));
    step++;
    if (step % 16 === 0) { bar++; if (bar % 8 === 0) prog = pick(PROGRESSIONS); }
  }

  // ---------------------------------------------------------------- Gino's own little noises (moods.js decides when)
  function voice(t, len, vol) { const g = gain(0); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + 0.08); g.gain.setTargetAtTime(0, t + len - 0.15, 0.08); g.connect(natureBus); return g; }
  const CUES = {
    hum(t) {          // a happy mm-mm-mmm little tune
      const notes = pick([[64, 67, 69, 67, 72], [60, 64, 67, 64, 65], [67, 69, 72, 69, 67]]);
      notes.forEach((n, i) => {
        const at = t + i * 0.42, o = ctx.createOscillator(), f = filt('lowpass', 900, 1.5), g = voice(at, 0.5, 0.05);
        o.type = 'triangle'; o.frequency.value = midi(n - 12); lfo(5.5, 4, o.frequency).stop(at + 0.6); o.connect(f); f.connect(g); o.start(at); o.stop(at + 0.6);
      });
    },
    yawn(t) {         // a long breathy aaah that slides down
      const o = ctx.createOscillator(), f = filt('bandpass', 700, 2.5), g = voice(t, 1.7, 0.07);
      o.type = 'sawtooth'; o.frequency.setValueAtTime(330, t); o.frequency.exponentialRampToValueAtTime(150, t + 1.6);
      f.frequency.setValueAtTime(900, t); f.frequency.exponentialRampToValueAtTime(400, t + 1.6); o.connect(f); f.connect(g); o.start(t); o.stop(t + 1.8);
    },
    rumble(t) {       // a deep gurgly tummy rumble
      const src = ctx.createBufferSource(); src.buffer = nodes.brownBuf; const f = filt('lowpass', 140, 4), g = voice(t, 1.6, 0.5);
      lfo(7, 60, f.frequency).stop(t + 1.7); src.connect(f); f.connect(g); src.start(t, Math.random() * 2); src.stop(t + 1.7);
    },
    grumble(t) {      // a low mrrrmph
      const o = ctx.createOscillator(), f = filt('lowpass', 520, 3), g = voice(t, 1.1, 0.06);
      o.type = 'sawtooth'; o.frequency.setValueAtTime(120, t); o.frequency.linearRampToValueAtTime(95, t + 1.1); lfo(13, 9, o.frequency, 'square').stop(t + 1.2); o.connect(f); f.connect(g); o.start(t); o.stop(t + 1.2);
    },
  };

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
    nodes.crackle.gain.setTargetAtTime(0.5, t, 1);
    master.gain.setTargetAtTime(on ? volume * volume : 0, t, 0.4);
    return { day, wet, snow };
  }
  function tick() {
    const m = mix(), now = ctx.currentTime, ahead = now + 0.5;
    if (musicOn) while (nextAt < ahead) { playStep(nextAt + (step % 2 ? STEP * SWING : 0)); nextAt += STEP; }
    else nextAt = now + 0.05;
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
      if (v) await ctx.resume();
      mix();
      if (!v) setTimeout(() => { if (!on) ctx.suspend(); }, 600);
    },
    setVolume(v) { volume = Math.min(1, Math.max(0, v)); mix(); },
    setMusic(v) { musicOn = v; mix(); },
    setNature(v) { natureOn = v; mix(); },
    update(s) { world = { ...world, ...s }; mix(); },
    cue(kind) { if (ctx && on && natureOn && CUES[kind]) CUES[kind](ctx.currentTime + 0.05); },   // hum, yawn, rumble, grumble
    pause(v) { if (ctx && on) v ? ctx.suspend() : ctx.resume(); },
    _debug: { get ctx() { return ctx; }, get master() { return master; } },
  };
}
