"""Gino on live TV: a 24/7 live stream of his habitat for YouTube, and TikTok Lives for special days.

Both ways of streaming are OFF until dad turns one on (see deploy/README.md, "Gino on live TV"):

  1. From dad's Windows PC (truly live, smooth). OBS Studio (free) shows the page /stream (static/stream.html) and
     sends it to YouTube or TikTok: his 3D world drawn live by the PC's graphics card, a camera that picks its own
     shots, his meadow's sounds and a caption of what he's doing. Only while the PC is on. Nothing in this file runs.

  2. From the server, day and night ("slow TV"). A server has no graphics card, so it can only draw his world at
     about one picture a second: far too slow to show it live. Instead the server keeps filming short scenes of
     his world as it is right now (30 seconds each, a few minutes' work apiece, like his TikTok videos) and plays
     the newest ones on a loop, without a break, with a live caption on top that says what he's doing at this
     very moment. Every scene is at most an hour or so old, so his time of day, weather, home and mood match.
     `gino stream youtube` (paste the stream key), then `gino stream on`. gino-stream.service runs this file.

Privacy: everything on screen comes from the same filtered, public slice of Gino as /live (/api/live and
photo.scene_state()), so a stream can't show anything his public website wouldn't. Viewers can chat with each other
in YouTube's chat, but Gino doesn't read or answer it, just like on /live.

The stream keys live only in /etc/gino/gino.env. They never reach the logs: _redact() hides them.

    python -m gino.stream run youtube                 stream to YouTube until stopped
    python -m gino.stream run tiktok --minutes 90     a TikTok Live that ends by itself
    python -m gino.stream test out.mp4 [seconds]      film one scene and make a short test video, send nothing
"""
import json
import logging
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import config, live

log = logging.getLogger("gino.stream")
router = APIRouter()

PLATFORMS = ("youtube", "tiktok")
SCENE_SECONDS = 30
KEEP_SCENES = 20        # the loop plays the newest 20 scenes (10 minutes) and keeps filming fresh ones
FRESH_MINUTES = 90      # older scenes are dropped even if no new ones arrived, so the time of day stays right
OVERLAY_EVERY = 10      # seconds between caption updates
SCENE_TIMEOUT = 90 * 60  # a 30-second scene takes a few minutes (more while a video films); 90 means stuck
PAGE_HEADERS = {**live.PAGE_HEADERS,
                "Content-Security-Policy": live.PAGE_HEADERS["Content-Security-Policy"] + "; font-src 'self'",
                "X-Robots-Tag": "noindex"}


@router.get("/stream", response_class=HTMLResponse)
def stream_page():
    """The TV picture. Public like /live (it shows only what /live shows), but not linked from anywhere."""
    return HTMLResponse((live.STATIC / "stream.html").read_text(encoding="utf-8"), headers=PAGE_HEADERS)


# ---------------------------------------------------------------- settings

def size(platform: str) -> tuple[int, int]:
    """YouTube gets a wide picture, TikTok a tall one (like a phone)."""
    w, h = (int(v) for v in config.STREAM_SIZE.lower().split("x"))
    return (min(w, h), max(w, h)) if platform == "tiktok" else (max(w, h), min(w, h))


def target(platform: str) -> str:
    """Where the video goes: the platform's RTMP address with the stream key on the end. Empty if not set up."""
    if platform == "youtube":
        key = config.STREAM_YOUTUBE_KEY
        return f"{config.STREAM_YOUTUBE_URL.rstrip('/')}/{key}" if key else ""
    if platform == "tiktok":
        url, key = config.STREAM_TIKTOK_URL, config.STREAM_TIKTOK_KEY
        return f"{url.rstrip('/')}/{key}" if url and key else ""
    return ""


def _redact(text: str) -> str:
    for s in (config.STREAM_YOUTUBE_KEY, config.STREAM_TIKTOK_KEY, config.STREAM_TIKTOK_URL):
        if len(s) >= 4:
            text = text.replace(s, "•••")
    return text


def ffmpeg() -> str:
    return config.FFMPEG or shutil.which("ffmpeg") or ""


def missing() -> list[str]:
    """What the server still needs before it can stream (empty when ready)."""
    out = [] if ffmpeg() else ["ffmpeg"]
    try:
        import playwright  # noqa: F401
    except ImportError:
        out.append("playwright")
    return out


def folder(platform: str):
    d = config.DATA_DIR / "stream" / ("tall" if platform == "tiktok" else "wide")
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- filming scenes (like his TikTok videos)

def _shots(state: dict, hour: float, rng: random.Random) -> list[dict]:
    """Three slow camera moves, 10 seconds each, at today's hour and weather. No words: the caption is live."""
    rain = "rain" if (state.get("weather") or {}).get("kind") == "rain" else None
    asleep = bool(state.get("asleep"))
    things = [h for h in state.get("habitat", []) if h.get("kind") not in ("path", "", None)]
    a = rng.uniform(-1.2, 1.2)
    close = {"around": "gino", "from": [6.5, 2.6, a], "to": [5.2, 2.2, a + rng.choice((-0.5, 0.5))]}
    medium = {"around": "gino", "from": [12, 5, a + 1], "to": [9, 4, a + 0.6]}
    wide = {"around": "home", "from": [32, 17, a], "to": [27, 14, a + 0.35]}
    cams = [close, medium, dict(close, **{"from": [7.5, 3.2, a - 0.8], "to": [6, 2.5, a - 0.3]})] if asleep \
        else [medium, wide, close]
    if things and not asleep and rng.random() < 0.6:
        t = rng.choice(things)
        cams[1] = {"around": [t["x"], t["y"]], "from": [9, 4.5, a], "to": [6.5, 3.2, a + 0.6]}
    rng.shuffle(cams)
    step = SCENE_SECONDS / len(cams)
    return [{"dur": step, "hour": [round((hour + i * step / 3600) % 24, 4), round((hour + (i + 1) * step / 3600) % 24, 4)],
             "asleep": asleep, "weather": rain, "tint": 0.35 if asleep else 0, "cam": c, "captions": []}
            for i, c in enumerate(cams)]


def scene_job(platform: str, rng: random.Random | None = None) -> dict:
    """What the video camera (static/clip.html) needs to film one scene of his world as it is now."""
    from . import clips, photo
    from .brain import local_now
    rng = rng or random.Random()
    state = photo.scene_state()  # filtered for the public, like his photos and videos
    state["habitat"] = live.state()["habitat"]
    now = local_now()
    shots = _shots(state, now.hour + now.minute / 60, rng)
    w, h = size(platform)
    return {"kind": "tv", "title": "", "fps": config.STREAM_FPS, "width": w, "height": h, "state": state,
            "shots": shots, "end": [], "end_seconds": 0, "quality": 0.9, "render_scale": config.STREAM_RENDER_SCALE,
            "sounds": clips._sound_plan(shots)}


def film_scene(platform: str) -> str:
    """Film one scene into the platform's folder. Returns the file name, or raises RuntimeError."""
    job = scene_job(platform)
    name = f"scene-{int(time.time())}.mp4"
    out = folder(platform) / name
    nice = ["nice", "-n", "15"] if shutil.which("nice") else []
    # its own process group: if a scene gets stuck, its browser and ffmpeg are stopped with it, not left running
    p = subprocess.Popen([*nice, sys.executable, "-m", "gino.clips", "render", str(out)], stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=str(config.ROOT),
                         start_new_session=True, env={**os.environ, "HOME": os.environ.get("TMPDIR", "/tmp")})
    try:
        _, err = p.communicate(json.dumps(job).encode(), timeout=SCENE_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            p.kill()
        _, err = p.communicate()
        err = b"it took too long. " + (err or b"")
    finally:
        (out.parent / (out.name + ".part.mp4")).unlink(missing_ok=True)
    if p.returncode or not out.exists() or out.stat().st_size < 10_000:
        out.unlink(missing_ok=True)
        raise RuntimeError("the camera didn't work: " + err.decode(errors="replace")[-400:])
    return name


def scenes(platform: str) -> list[str]:
    """The scenes to play, oldest first (so the day moves forward). Old and stale ones are tidied away."""
    files = sorted(folder(platform).glob("scene-*.mp4"), key=lambda f: f.name)
    for f in files[:-KEEP_SCENES]:
        f.unlink(missing_ok=True)
    files = files[-KEEP_SCENES:]
    fresh = [f for f in files if time.time() - f.stat().st_mtime < FRESH_MINUTES * 60]
    if fresh and len(fresh) < len(files):  # keep stale ones only while there's nothing newer to show
        for f in set(files) - set(fresh):
            f.unlink(missing_ok=True)
        files = fresh
    return [f.name for f in files]


def write_playlist(platform: str) -> bool:
    """The loop: a playlist that ends by pointing at itself, so ffmpeg reads it again (with any new scenes) each
    time round and the stream never stops. Returns False if there's nothing to play yet."""
    names = scenes(platform)
    if not names:
        return False
    d = folder(platform)
    body = "ffconcat version 1.0\n" + "".join(f"file '{n}'\n" for n in names) + "file 'loop.ffconcat'\n"
    tmp = d / "loop.ffconcat.part"
    tmp.write_text(body)
    os.replace(tmp, d / "loop.ffconcat")
    return True


# ---------------------------------------------------------------- the live caption on top

class Caption:
    """A see-through picture of the caption and mood bars (/stream?overlay=1), refreshed every few seconds."""

    def __init__(self, platform: str):
        self.platform, self.path = platform, folder(platform) / "caption.png"
        self._pw = self.browser = self.page = None

    def open(self) -> None:
        from playwright.sync_api import sync_playwright
        w, h = size(self.platform)
        self._pw = sync_playwright().start()
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        self.browser = self._pw.chromium.launch(
            args=["--no-sandbox"], executable_path=config.PHOTO_CHROMIUM or None,
            proxy={"server": proxy, "bypass": "127.0.0.1,localhost"} if proxy else None)
        self.page = self.browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1,
                                          timezone_id=config.TIMEZONE or None)
        self.page.goto(f"http://127.0.0.1:{config.PORT}/stream?overlay=1", wait_until="load", timeout=60_000)
        self.page.wait_for_timeout(2500)  # fonts and the first answer from /api/live
        self.snap()

    def snap(self) -> None:
        tmp = self.path.with_name("caption.part.png")
        self.page.screenshot(path=str(tmp), omit_background=True, type="png")
        os.replace(tmp, self.path)

    def close(self) -> None:
        for fn in (lambda: self.browser and self.browser.close(), lambda: self._pw and self._pw.stop()):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass


def ffmpeg_cmd(platform: str, dest: str, seconds: float = 0) -> list[str]:
    """Play the loop of scenes in real time, lay the live caption on top and send it out. Settings follow
    YouTube's advice for live video: H.264, a keyframe every 2 seconds, steady bitrate, AAC sound at 44.1 kHz."""
    d, fps, kbps = folder(platform), config.STREAM_FPS, config.STREAM_KBPS
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
           "-re", "-f", "concat", "-safe", "0", "-i", str(d / "loop.ffconcat"),
           "-re", "-f", "image2", "-loop", "1", "-framerate", "1", "-i", str(d / "caption.png"),
           "-filter_complex", f"[0:v]fps={fps}[b];[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
           "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k",
           "-bufsize", f"{kbps * 2}k", "-g", str(fps * 2), "-keyint_min", str(fps * 2), "-sc_threshold", "0",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    if seconds:
        cmd += ["-t", f"{seconds:.1f}"]
    return cmd + (["-f", "flv", dest] if dest.startswith("rtmp") else ["-movflags", "+faststart", dest])


# ---------------------------------------------------------------- running it

_stop = threading.Event()


def _filmer(platform: str) -> None:
    """Keeps filming fresh scenes, one after another, for as long as the stream runs."""
    wait = 30
    while not _stop.is_set():
        try:
            t0 = time.time()
            name = film_scene(platform)
            write_playlist(platform)
            log.info("Filmed a new scene for the stream (%s, %.0f s of work)", name, time.time() - t0)
            wait = 30
        except Exception as e:  # noqa: BLE001
            log.warning("Couldn't film a scene, trying again in %d s: %s", wait, e)
            _stop.wait(wait)
            wait = min(900, wait * 2)


def _pump(p: subprocess.Popen, tail: list[str]) -> None:
    for raw in p.stderr:
        line = _redact(raw.decode(errors="replace").rstrip())
        if line:
            tail.append(line)
            del tail[:-20]


def run(platform: str, minutes: float = 0) -> int:
    """Stream until stopped (or for `minutes`). Starts itself again when something breaks."""
    if platform not in PLATFORMS:
        raise SystemExit(f"Unknown place to stream to: {platform}")
    dest = target(platform)
    if not dest:
        raise SystemExit(f"No {platform} stream key yet. Set it up with: gino stream {platform}")
    if missing():
        raise SystemExit("The server isn't ready to stream (missing: " + ", ".join(missing()) + "). Run: gino stream on")
    signal.signal(signal.SIGTERM, lambda *_: _stop.set())
    signal.signal(signal.SIGINT, lambda *_: _stop.set())
    ends = time.time() + minutes * 60 if minutes else 0
    threading.Thread(target=_filmer, args=(platform,), daemon=True, name="tv-filmer").start()
    while not write_playlist(platform) and not _stop.is_set():  # the very first time: wait for a first scene
        log.info("Filming the first scene before going live (a few minutes)...")
        _stop.wait(30)
    wait = 15
    while not _stop.is_set() and not (ends and time.time() >= ends):
        cap, enc, started, tail = Caption(platform), None, time.time(), []
        try:
            cap.open()
            enc = subprocess.Popen(ffmpeg_cmd(platform, dest), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, cwd=str(folder(platform)))
            threading.Thread(target=_pump, args=(enc, tail), daemon=True).start()
            log.info("📺 Gino is live on %s", platform)
            while not _stop.is_set():
                if ends and time.time() >= ends:
                    log.info("The %s live has reached its time. Goodbye for now!", platform)
                    break
                if enc.poll() is not None:
                    raise RuntimeError("the stream stopped" + (": " + " / ".join(tail[-3:]) if tail else ""))
                cap.snap()
                _stop.wait(OVERLAY_EVERY)
            wait = 15
        except Exception as e:  # noqa: BLE001
            log.warning("Stream trouble, trying again in %d s: %s", wait, _redact(str(e))[:500])
        finally:
            if enc and enc.poll() is None:
                enc.terminate()
                try:
                    enc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    enc.kill()
            cap.close()
        if not _stop.is_set() and not (ends and time.time() >= ends) and time.time() - started < 120:
            _stop.wait(wait)  # it broke quickly: wait a bit longer each time (up to 10 minutes)
            wait = min(600, wait * 2)
    _stop.set()
    return 0


def test(out: str, seconds: float = 20, platform: str = "youtube") -> int:
    """Film one fresh scene and make a short test video with the live caption: exactly like the real stream,
    but saved to a file instead of sent anywhere."""
    if missing():
        raise SystemExit("The server isn't ready to stream (missing: " + ", ".join(missing()) + "). Run: gino stream on")
    t0 = time.time()
    print("Filming a scene of Gino's world (this takes a few minutes on a server)...", flush=True)
    film_scene(platform)
    write_playlist(platform)
    print(f"Filmed it in {time.time() - t0:.0f} s. Adding the live caption...", flush=True)
    cap = Caption(platform)
    try:
        cap.open()
        p = subprocess.run(ffmpeg_cmd(platform, os.path.abspath(out), seconds=seconds), capture_output=True,
                           cwd=str(folder(platform)), timeout=seconds + 180)
    finally:
        cap.close()
    if p.returncode or not os.path.exists(out) or os.path.getsize(out) < 10_000:
        print("The test didn't work:", _redact(p.stderr.decode(errors="replace"))[-800:], file=sys.stderr)
        return 1
    print(f"Saved a {seconds:.0f}-second test to {out}. Nothing was sent anywhere.")
    return 0


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    if argv[:1] == ["run"] and len(argv) >= 2:
        minutes = float(argv[argv.index("--minutes") + 1]) if "--minutes" in argv else 0
        return run(argv[1], minutes)
    if argv[:1] == ["test"] and len(argv) >= 2:
        platform = "tiktok" if "--tall" in argv else "youtube"
        rest = [a for a in argv[2:] if a != "--tall"]
        return test(argv[1], float(rest[0]) if rest else 20, platform)
    print(__doc__.rsplit("\n\n", 1)[-1])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
