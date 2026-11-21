"""Gino's own video editor: the finishing touch for his clips, done on the server, day and night.

Dad can choose who polishes the videos (`gino polish pc|server|off`, GINO_POLISHER):
  pc      FilmCraft on dad's Windows PC does it (see clips.py). When the PC is off, or hasn't picked a clip up
          after a while, the server polishes it instead, so a video never waits forever. This is the default.
  server  the server polishes every new clip straight away. The PC script is told there's nothing to do.
  off     videos stay exactly as Gino filmed them.

What the server's polish does (ffmpeg, plus Piper for the voice; no AI service and nothing from his budget):
  - a narrator reads the captions aloud with a natural-sounding offline voice (Piper), each line when it appears.
    Lines Gino says himself (his speech bubbles) are read in a higher, smaller "Gino" voice.
  - his meadow sounds dip under the narrator, then the whole mix is set to the loudness TikTok expects
  - the picture is upscaled to 1080x1920, sharpened and given a warm, golden colour grade with a soft vignette
  - a short fade in from black and out at the end

The words come from the clip's script, which clips.plan() already passed through public.check().
The voice is optional: without it (or with GINO_POLISH_NARRATOR=0) the clip still gets the picture and sound polish.
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave

from . import clips, config, db

log = logging.getLogger("gino.polish")
MODES = ("pc", "server", "off")
PC_GRACE = 40 * 60     # in "pc" mode, a clip FilmCraft hasn't finished 40 minutes after filming started goes to the server
TIMEOUT = 20 * 60      # the server's polish takes a minute or three; give up after 20
WORKING = "server: polishing"
_lock = threading.Lock()
_reset = False


def mode() -> str:
    return config.POLISHER if config.POLISHER in MODES else "pc"


def available() -> bool:
    """Can the server polish at all? (It needs the video camera's ffmpeg.)"""
    return config.CLIPS_ON and bool(clips.ffmpeg())


def narrator() -> str:
    """The narrator's voice file, or '' when there's no narrator."""
    v = config.POLISH_VOICE
    if not (config.POLISH_NARRATOR and v and os.path.exists(v)):
        return ""
    import importlib.util
    return v if importlib.util.find_spec("piper") else ""


def expected(cid: int) -> bool:
    """Will someone polish this clip soon? (TikTok's automatic send waits for it when so.)"""
    m = mode()
    if m == "off":
        return False
    if m == "server":
        return available()
    return clips.polisher_on() or available()


def due(now: float | None = None) -> list[int]:
    """Clips the server should polish now, oldest first."""
    now = now or time.time()
    m = mode()
    if m == "off" or not available():
        return []
    rows = db.q("SELECT id, ts FROM clips WHERE status='ready' AND filename!='' AND polished='' AND polish_note='' "
                "AND tiktok_status='' AND ts>? ORDER BY id", (now - clips.POLISH_DAYS * 86400,))
    if m == "pc" and clips.polisher_on(now):  # dad's PC is on: let FilmCraft have a go first
        rows = [r for r in rows if r["ts"] < now - PC_GRACE]
    return [r["id"] for r in rows if clips.path(r["id"], raw=True)]


def maybe_polish(now: float | None = None) -> int | None:
    """Called from his heartbeat and after each new clip: start polishing the next clip that needs it."""
    global _reset
    if not _reset:  # a restart in the middle of a polish: let it be picked up again
        _reset = True
        db.x("UPDATE clips SET polish_note='' WHERE polish_note=?", (WORKING,))
    if _lock.locked():
        return None
    for cid in due(now):
        db.x("UPDATE clips SET polish_note=? WHERE id=? AND polished='' AND polish_note=''", (WORKING, cid))
        if db.q("SELECT 1 FROM clips WHERE id=? AND polish_note=?", (cid, WORKING)):
            threading.Thread(target=_polish, args=(cid,), daemon=True, name=f"polish-{cid}").start()
            return cid
    return None


def _polish(cid: int) -> None:
    with _lock, clips._busy:  # never at the same time as filming: the server only has two small processors
        started = time.time()
        rows = db.q("SELECT kind, script, polished FROM clips WHERE id=?", (cid,))
        src = clips.path(cid, raw=True)
        if not rows or not src or rows[0]["polished"]:
            db.x("UPDATE clips SET polish_note='' WHERE id=? AND polish_note=?", (cid, WORKING))
            return
        try:
            script = json.loads(rows[0]["script"]) if rows[0]["script"] else {}
        except ValueError:
            script = {}
        name = f"gino-{cid}-{rows[0]['kind']}-finished.mp4"  # not the PC's file name, so neither overwrites the other
        out = clips.CLIPS_DIR / name
        err = ""
        try:
            p = subprocess.run(["nice", "-n", "10", sys.executable, "-m", "gino.polish", "make", str(src), str(out)],
                               input=json.dumps({"script": script, "voice": narrator()}).encode(),
                               capture_output=True, timeout=TIMEOUT, cwd=str(config.ROOT))
            ok = p.returncode == 0 and out.exists() and out.stat().st_size > 10_000
            err = p.stderr.decode(errors="replace")[-1500:]
        except (OSError, subprocess.TimeoutExpired) as e:
            ok, err = False, str(e)
        if ok and db.q("SELECT 1 FROM clips WHERE id=? AND polished='' AND tiktok_status=''", (cid,)):
            db.x("UPDATE clips SET polished=?, polished_by='server', polish_note='' WHERE id=?", (name, cid))
            db.event("clip", f"his clip got its finishing touch on the server in {int(time.time() - started)} s")
            log.info("Clip %s polished on the server in %.0f s", cid, time.time() - started)
        else:  # it failed, or FilmCraft (or TikTok) got there first
            if not ok:
                log.warning("Polishing clip %s failed: %s", cid, err)
            out.unlink(missing_ok=True)
            db.x("UPDATE clips SET polish_note=? WHERE id=? AND polish_note=?",
                 ("" if ok else "server failed", cid, WORKING))


# ---------------------------------------------------------------- the editing itself (separate process)

_NOT_SPOKEN = re.compile(r"[^\w\s.,!?'’:;\-]")


def speakable(text: str) -> str:
    """What the narrator reads: no emoji, hashtags or fancy quotes."""
    text = re.sub(r"#\w+", "", str(text or "")).replace("…", ".").replace("“", "").replace("”", "")
    text = " ".join(_NOT_SPOKEN.sub(" ", text).split()).strip(" -:;,")
    return text if re.search(r"[A-Za-z]{2}", text) else ""


def timing(lines: list[dict], lengths: list[float], seconds: float) -> list[float | None]:
    """When each spoken line starts: as its caption appears, never over the line before, never past the end."""
    out, free = [], 0.0
    for line, length in zip(lines, lengths):
        start = max(float(line.get("at", 0)) + 0.15, free + 0.2)
        if length <= 0 or start + length > seconds - 0.4:
            out.append(None)
            continue
        out.append(round(start, 3))
        free = start + length
    return out


def _speak(voice_path: str, lines: list[dict], folder: str) -> list[tuple[str, float, bool]]:
    """Each line as a WAV file: (path, seconds, said by Gino himself)."""
    from piper import PiperVoice, SynthesisConfig
    voice = PiperVoice.load(voice_path)
    calm = SynthesisConfig(length_scale=1.08, noise_scale=0.6, noise_w_scale=0.7)
    out = []
    for i, line in enumerate(lines):
        f = os.path.join(folder, f"line{i}.wav")
        with wave.open(f, "wb") as w:
            voice.synthesize_wav(line["say"], w, syn_config=calm)
        with wave.open(f) as w:
            secs = w.getnframes() / float(w.getframerate())
        if line.get("speech"):  # Gino's own voice is higher and quicker
            secs /= 1.12
        out.append((f, secs, bool(line.get("speech"))))
    return out


def _duration(path: str) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 20.0


LOOK = ("scale=1080:1920:flags=lanczos,"
        "eq=contrast=1.05:saturation=1.14:brightness=0.015,"
        "colorbalance=rs=0.02:bs=-0.03:rm=0.02:bm=-0.02:rh=0.04:gh=0.015:bh=-0.03,"
        "vignette=angle=PI/9,"
        "unsharp=5:5:0.7:5:5:0.0")


def make(src: str, out: str, script: dict, voice: str = "") -> None:
    seconds = _duration(src)
    lines = [{**l, "say": speakable(l.get("text", ""))} for l in (script or {}).get("lines", [])]
    lines = [l for l in lines if l["say"]]
    with tempfile.TemporaryDirectory(prefix="gino-polish-") as tmp:
        spoken = _speak(voice, lines, tmp) if voice and lines else []
        starts = timing(lines, [s[1] for s in spoken], seconds) if spoken else []
        args, parts, voices = [], [], []
        for (f, _, gino), start in zip(spoken, starts):
            if start is None:
                continue
            n = 1 + len(voices)
            args += ["-i", f]
            pitch = "asetrate=22050*1.2,aresample=22050,atempo=0.935," if gino else ""
            parts.append(f"[{n}:a]aresample=22050,{pitch}highpass=f=90,"
                         f"adelay={int(start * 1000)}:all=1,apad[v{n}]")
            voices.append(f"[v{n}]")
        fade = f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0, seconds - 0.5):.2f}:d=0.5"
        parts.append(f"[0:v]{LOOK},{fade},format=yuv420p[vout]")
        tail = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
        if voices:
            parts.append(f"{''.join(voices)}amix=inputs={len(voices)}:normalize=0,volume=1.9,"
                         f"acompressor=threshold=0.2:ratio=3:attack=5:release=120,asplit[nar][key]")
            parts.append("[0:a]aresample=48000[bed0]")
            parts.append("[bed0][key]sidechaincompress=threshold=0.02:ratio=10:attack=40:release=600:makeup=1[bed]")
            parts.append(f"[bed][nar]amix=inputs=2:normalize=0:duration=first,{tail}[aout]")
        else:
            parts.append(f"[0:a]{tail}[aout]")
        cmd = [clips.ffmpeg() or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, *args,
               "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-t", f"{seconds:.3f}", "-movflags", "+faststart", out + ".part.mp4"]
        subprocess.run(cmd, check=True)
        os.replace(out + ".part.mp4", out)


if __name__ == "__main__":
    if sys.argv[1:2] == ["make"] and len(sys.argv) == 4:  # used by _polish(): the job comes on stdin
        job = json.loads(sys.stdin.read() or "{}")
        make(sys.argv[2], sys.argv[3], job.get("script") or {}, job.get("voice") or "")
    elif sys.argv[1:2] == ["status"]:
        print(json.dumps({"mode": mode(), "narrator": bool(narrator()), "can_polish": available()}))
    else:
        print("usage: python -m gino.polish make in.mp4 out.mp4 < job.json   |   python -m gino.polish status")
