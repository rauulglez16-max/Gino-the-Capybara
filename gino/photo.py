"""Gino's camera: a real picture of his 3D world, for his Bluesky posts.

The server opens its own page (static/photo.html) in a headless Chromium, hands it a filtered copy of
Gino's state, and screenshots it. It's the same 3D world dad sees, so the photo shows what Gino is really
doing, where he really is, and what he really built. No AI image generation, so it costs nothing.

Only public-safe things go into the picture: drawings he already put on a public page, item names that pass
public.check() (they only show up in hover tooltips anyway), and nothing from chats, memories or journals.

Needs Playwright + Chromium on the server: `gino photos on` installs them. Off (GINO_PHOTOS=0) by default.
The browser runs in a separate process with a timeout, so a stuck render never blocks Gino's turn.
"""
import base64
import json
import logging
import os
import subprocess
import sys
import threading

from . import config, db, public, vitals

log = logging.getLogger("gino.photo")
MAX_BYTES = 950_000  # Bluesky refuses images over 1,000,000 bytes
SIZE = (1200, 900)
_lock = threading.Lock()  # one photo at a time: Chromium is heavy on a small server


def available() -> bool:
    if not config.PHOTOS_ON:
        return False
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _clean(text, limit: int, fallback: str = "") -> str:
    text = " ".join(str(text or "").split())[:limit]
    return fallback if not text or public.check(text) else text


def scene_state() -> dict:
    """What the camera page gets: enough to draw his world, nothing private."""
    from .brain import local_now
    body = vitals.load()
    habitat = [{**it, "name": _clean(it["name"], 80, it["kind"] or "thing"),
                "description": _clean(it["description"], 200), "emoji": _clean(it["emoji"], 8)}
               for it in db.q("SELECT id,name,emoji,x,y,description,kind,color,size FROM habitat ORDER BY id")]
    art = [r["filename"] for r in db.q(
        "SELECT DISTINCT c.filename, c.ts FROM creations c JOIN posts p ON p.creation_id=c.id "
        "WHERE p.kind='page' AND c.kind='svg' ORDER BY c.ts DESC LIMIT 6")]
    return {
        "pos": body.get("pos", [7, 5]), "asleep": vitals.is_asleep(body), "thinking": False,
        "activity": _clean(body.get("activity"), 80, "pottering about"),
        "emotion": _clean(body.get("emotion"), 30, "calm"),
        "vitals": vitals.snapshot(body), "weather": vitals.weather(local_now()),
        "habitat": habitat, "art": art,
    }


def take(shot: str = "selfie") -> bytes:
    """Take a photo now. Returns JPEG bytes, or raises RuntimeError with a reason."""
    if not available():
        raise RuntimeError("the camera isn't set up on this server")
    job = json.dumps({"state": scene_state(), "shot": "wide" if shot == "wide" else "selfie"})
    with _lock:
        try:
            r = subprocess.run([sys.executable, "-m", "gino.photo", "shoot"], input=job.encode(), capture_output=True,
                               timeout=config.PHOTO_TIMEOUT, cwd=str(config.ROOT),
                               env={**os.environ, "HOME": os.environ.get("TMPDIR", "/tmp")})
        except subprocess.TimeoutExpired:
            raise RuntimeError("the camera took too long") from None
    if r.returncode != 0 or not r.stdout.startswith(b"\xff\xd8"):
        log.warning("photo failed: %s", r.stderr.decode(errors="replace")[-800:])
        raise RuntimeError("the camera didn't work this time")
    return r.stdout


def save(post_id: int, jpeg: bytes) -> str:
    folder = config.DATA_DIR / "photos"
    folder.mkdir(exist_ok=True)
    name = f"{int(post_id)}.jpg"
    (folder / name).write_bytes(jpeg)
    return name


# ---------------------------------------------------------------- the browser side (separate process)

def _shoot(job: dict) -> bytes:
    from playwright.sync_api import sync_playwright
    url = f"http://127.0.0.1:{config.PORT}/static/photo.html"
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"]
    with sync_playwright() as p:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        browser = p.chromium.launch(args=args, executable_path=config.PHOTO_CHROMIUM or None,
                                    proxy={"server": proxy, "bypass": "127.0.0.1,localhost"} if proxy else None)
        try:
            page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1,
                                    timezone_id=config.TIMEZONE or None)
            local = os.environ.get("GINO_THREE_DIR")  # for offline testing: serve three.js from a local copy
            if local:
                page.route("https://cdn.jsdelivr.net/npm/three@*/**", lambda route: route.fulfill(
                    path=os.path.join(local, route.request.url.split("/", 5)[-1]), content_type="text/javascript"))
            page.goto(url, wait_until="load", timeout=45_000)
            page.wait_for_function("window.cameraReady === true", timeout=30_000)
            url = page.evaluate("job => takePhoto(job)", {**job, "key": config.PASSWORD, "maxBytes": MAX_BYTES})
            return base64.b64decode(url.split(",", 1)[1])
        finally:
            browser.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["shoot"]:
        sys.stdout.buffer.write(_shoot(json.loads(sys.stdin.read())))
    elif sys.argv[1:2] == ["test"]:  # `python -m gino.photo test out.jpg` takes a picture without posting it
        logging.basicConfig()
        out = sys.argv[2] if len(sys.argv) > 2 else "gino-photo-test.jpg"
        try:
            data = take(sys.argv[3] if len(sys.argv) > 3 else "selfie")
        except RuntimeError as e:
            sys.exit(f"No photo: {e}")
        with open(out, "wb") as f:
            f.write(data)
        print(f"Saved a {len(data) // 1024} KB photo to {out}. Nothing was posted.")
    else:
        print("usage: python -m gino.photo test [out.jpg] [selfie|wide]")
