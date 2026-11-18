"""Gino's video camera: short vertical clips of his life (9:16, about 20 seconds, with his meadow's sounds).

Made for TikTok, Reels and Shorts. The server films his real 3D world in a headless Chromium
(static/clip.html), one frame at a time, and ffmpeg turns the frames and his day/night/rain sounds into an MP4.
No AI image or video generation and no AI call, so a clip costs nothing from his daily budget (it only uses
the server's computer for a few minutes).

Four kinds of clip, each a little story told from his own records:
  day     "A day in Gino's life": morning to night in 20 seconds, with things he did today
  night   "What Gino does while you sleep": a night timelapse, then he wakes up
  dream   he sleeps, dreams, and then the painting he made of the dream appears
  made    the newest thing he built or painted, and the story behind it

Privacy: every word that goes into a clip or its caption goes through public.check(), the same filter as his
public website, and only drawings he already put on a public page are shown. Nothing from chats, memories or
journals. Dad sees the finished clips on his private page and decides what to post (see tiktok.py).

Off by default (GINO_CLIPS=0). `gino clips on` installs what it needs on the server.
"""
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from . import config, db, keepsakes, live, photo, public

log = logging.getLogger("gino.clips")
KINDS = ("day", "night", "dream", "made")
KIND_NAMES = {"day": "A day in Gino's life", "night": "While you sleep", "dream": "A dream, then a painting",
              "made": "Something he made"}
SOUNDS = config.ROOT / "gino" / "sounds"
CLIPS_DIR = config.DATA_DIR / "clips"
END_SECONDS = 2.6
KEEP = 40  # the newest clips are kept; older video files are deleted to save disk space
HASHTAGS = "#capybara #capybaras #cozy #aiart #virtualpet #ai #cute"

progress: dict[int, str] = {}  # clip id -> "filming 120 of 480 frames", for dad's page
_busy = threading.Lock()


def _schema() -> None:
    db.x("""CREATE TABLE IF NOT EXISTS clips (
      id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
      caption TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'making'
        CHECK (status IN ('making','ready','failed')),
      filename TEXT NOT NULL DEFAULT '', seconds REAL NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
      made_by TEXT NOT NULL DEFAULT 'auto', source TEXT NOT NULL DEFAULT '',
      tiktok_status TEXT NOT NULL DEFAULT '', tiktok_id TEXT NOT NULL DEFAULT '', tiktok_ts REAL,
      tiktok_note TEXT NOT NULL DEFAULT '',
      script TEXT NOT NULL DEFAULT '', polished TEXT NOT NULL DEFAULT '', polish_note TEXT NOT NULL DEFAULT '')""")
    have = {r["name"] for r in db.q("PRAGMA table_info(clips)")}
    # script: the captions and when they show (for the polisher); polished: the FilmCraft version's file name
    for col in ("script", "polished", "polish_note"):
        if col not in have:
            db.x(f"ALTER TABLE clips ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")


_schema()


def ffmpeg() -> str:
    return config.FFMPEG or shutil.which("ffmpeg") or ""


def available() -> bool:
    if not config.CLIPS_ON or not ffmpeg():
        return False
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------- what's worth telling (all public-safe)

def _clean(text, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return "" if not text or public.check(text) else text


def _public_art(since: float = 0, dream: bool | None = None) -> list[dict]:
    """Drawings he put on a public page (newest first). dream=True: only dream paintings."""
    sql = ("SELECT DISTINCT c.id, c.ts, c.title, c.dream_id FROM creations c JOIN posts p ON p.creation_id=c.id "
           "WHERE p.kind='page' AND c.kind='svg' AND c.ts>?")
    if dream is True:
        sql += " AND c.dream_id IS NOT NULL"
    rows = db.q(sql + " ORDER BY c.ts DESC LIMIT 10", (since,))
    return [{**r, "title": _clean(r["title"], 60)} for r in rows if _clean(r["title"], 60)]


def _built(since: float) -> list[dict]:
    out = []
    for it in db.q("SELECT id,ts,name,emoji,x,y,kind,story,origin FROM habitat WHERE ts>? ORDER BY ts DESC LIMIT 8",
                   (since,)):
        name = live._item_name(it["name"], it["kind"] or "")
        story = keepsakes.public_story(it) if it["story"] else ""
        if story == keepsakes.PRIVATE_STORY:
            story = ""
        out.append({**it, "name": name, "story": _clean(story, 110)})
    return out


def _already(source: str) -> bool:
    return bool(db.q("SELECT 1 FROM clips WHERE source=? AND status!='failed'", (source,)))


def _feeling(state: dict) -> str:
    e = state.get("emotion") or ""
    return f"Feeling {e} today" if e and e not in ("calm",) else ""


def best_kind(now: float | None = None) -> str:
    """Pick today's story: a fresh dream painting beats a new thing he built, which beats a plain day."""
    now = now or time.time()
    fresh = now - 3 * 86400
    if any(not _already(f"art:{a['id']}") for a in _public_art(fresh, dream=True)):
        return "dream"
    if any(not _already(f"item:{b['id']}") for b in _built(fresh)) or \
            any(not _already(f"art:{a['id']}") for a in _public_art(fresh)):
        return "made"
    return "night" if int(now // 86400) % 3 == 0 else "day"


# ---------------------------------------------------------------- the script for one clip

def _end() -> list[str]:
    site = re.sub(r"^https?://", "", config.PUBLIC_URL or "").rstrip("/") or "ginothecapybara.com"
    return ["Gino the capybara 🌿", f"An AI capybara living his own life · {site}"]


def plan(kind: str, now: float | None = None) -> dict:
    """The shots, captions and the post's text for one clip. Everything in it is safe for the whole world."""
    now = now or time.time()
    state = photo.scene_state()
    state["habitat"] = live.state()["habitat"]  # names and stories already filtered for visitors
    rain = "rain" if (state.get("weather") or {}).get("kind") == "rain" else None
    since = now - 86400
    built, art = _built(since), _public_art(since)
    lines = [f"He built a {b['name']} {b['emoji']}".strip() for b in built[:2]]
    lines += [f"He painted '{a['title']}' 🎨" for a in art[:1]]
    note = _clean(live._diary_line(), 90)
    source, art_url, title = "", "", KIND_NAMES.get(kind, "")

    if kind == "dream":
        pics = [a for a in _public_art(now - 7 * 86400, dream=True) if not _already(f"art:{a['id']}")] or \
            _public_art(dream=True)
        if not pics:
            kind = "night"
        else:
            p = pics[0]
            source, art_url = f"art:{p['id']}", f"/blog/art/{p['id']}.svg"
            shots = [
                {"dur": 6.5, "hour": [23.2, 24.6], "asleep": True, "tint": 0.6, "weather": rain,
                 "cam": {"around": "gino", "from": [11, 6, 0.9], "to": [4.8, 2.2, 0.5]},
                 "captions": [{"text": "Shh… Gino is asleep 💤", "at": 3.2, "y": "bottom"}]},
                {"dur": 5.5, "hour": [1.5, 2.5], "asleep": True, "tint": 1.0, "weather": rain,
                 "cam": {"around": "gino", "from": [4.4, 1.6, 0.2], "to": [3.6, 1.4, -0.2]},
                 "captions": [{"text": "…and he's dreaming 🌙", "at": 0.4, "y": "bottom"}]},
                {"dur": 7.5, "hour": [7.5, 8.5], "asleep": False, "activity": "painting",
                 "cam": {"around": "gino", "from": [7, 3, -0.4], "to": [9, 4, -0.7]}, "art": art_url,
                 "captions": [{"text": "In the morning, he painted it:", "at": 0.4, "until": 3.6, "y": "top"},
                              {"text": f"'{p['title']}'", "at": 3.4, "y": "bottom"}]},
            ]
            text = (f"Last night Gino had a dream, so in the morning he painted it: '{p['title']}' 🌙🎨 "
                    "He's an AI capybara who lives his own life, all on his own.")
            title = "Gino dreamed it, then painted it"

    if kind == "made":
        item = next((b for b in _built(now - 3 * 86400) if not _already(f"item:{b['id']}")), None)
        pic = next((a for a in _public_art(now - 3 * 86400) if not _already(f"art:{a['id']}")), None)
        if item:
            source = f"item:{item['id']}"
            spot = [item["x"], item["y"]]
            story = f"“{item['story']}”" if item["story"] else "Nobody told him to. He just wanted one."
            shots = [
                {"dur": 5.0, "hour": [10, 11], "weather": rain,
                 "cam": {"around": "home", "from": [36, 22, -0.9], "to": [28, 15, -0.6]},
                 "captions": [{"text": "Gino had an idea… 💡", "at": 1.2, "y": "bottom"}]},
                {"dur": 7.5, "hour": [11, 12.5], "weather": rain,
                 "cam": {"around": spot, "from": [9, 5, 0.3], "to": [6, 3, 1.1]},
                 "captions": [{"text": f"He built a {item['name']} {item['emoji']}".strip(), "at": 0.4, "until": 4.2,
                               "y": "bottom"},
                              {"text": story, "at": 4.0, "y": "bottom"}]},
                {"dur": 6.5, "hour": [17.2, 18.4], "weather": rain,
                 "cam": {"around": "gino", "from": [8, 3.5, 0.8], "to": [5, 2.2, 0.3]},
                 "captions": [{"text": "Proud capybara 🥹", "at": 1.0, "y": "bottom"}]},
            ]
            why = f"In his words: “{item['story']}”" if item["story"] else "Nobody asked him to."
            text = (f"Gino built a {item['name']} {item['emoji']} today. {why} "
                    "He's an AI capybara who decides everything himself.")
            title = f"Gino built a {item['name']}"
        elif pic:
            source, art_url = f"art:{pic['id']}", f"/blog/art/{pic['id']}.svg"
            shots = [
                {"dur": 6.0, "hour": [9.5, 10.5], "weather": rain,
                 "cam": {"around": "gino", "from": [14, 8, 1.2], "to": [6, 2.6, 0.6]},
                 "captions": [{"text": "Gino felt like painting today 🎨", "at": 1.2, "y": "bottom"}]},
                {"dur": 7.0, "hour": [11, 12], "weather": rain, "art": art_url,
                 "cam": {"around": "gino", "from": [6, 2.6, 0.6], "to": [7, 3, 0.1]},
                 "captions": [{"text": f"'{pic['title']}'", "at": 1.6, "y": "bottom"}]},
                {"dur": 6.0, "hour": [17.4, 18.4], "weather": rain,
                 "cam": {"around": "home", "from": [26, 13, -0.3], "to": [30, 16, -0.8]},
                 "captions": [{"text": "Nobody asked him to. He just wanted to.", "at": 0.8, "y": "bottom"}]},
            ]
            text = f"Gino painted '{pic['title']}' today 🎨 He's an AI capybara who makes art when he feels like it."
            title = f"Gino painted '{pic['title']}'"
        else:
            kind = "day"

    if kind == "night":
        shots = [
            {"dur": 5.5, "hour": [20.5, 22.5], "weather": rain,
             "cam": {"around": "home", "from": [30, 16, -0.4], "to": [24, 12, -0.9]},
             "captions": [{"text": "You go to bed… 🌙", "at": 1.0, "y": "bottom"}]},
            {"dur": 7.0, "hour": [23, 28.5], "asleep": True, "tint": 0.5, "weather": rain, "speed": 1.6,
             "cam": {"around": "gino", "from": [9, 5, 1.4], "to": [5, 2.4, 0.4]},
             "captions": [{"text": "Gino curls up under the stars ✨", "at": 0.6, "until": 3.6, "y": "bottom"},
                          {"text": (f"Tonight's dream: '{art[0]['title']}'" if art and art[0].get('dream_id')
                                    else "He dreams about his day"), "at": 3.6, "y": "bottom"}]},
            {"dur": 6.5, "hour": [6.4, 8.2], "asleep": False, "activity": "having a big stretch",
             "cam": {"around": "gino", "from": [5, 2.2, 0.2], "to": [9, 4, 0.9]},
             "captions": [{"text": "…and wakes up ready for a new day ☀️", "at": 0.8, "y": "bottom"}]},
        ]
        text = ("What Gino does while you sleep 🌙 He's an AI capybara who lives in his own little world, "
                "day and night, even when nobody's watching.")
        title = "What Gino does while you sleep"

    if kind == "day":
        extra = lines + ([note] if note else []) + ([_feeling(state)] if _feeling(state) else [])
        say = (extra + ["He decides everything himself", "Snack time 🍉", "Just vibing 🌿"])[:3]
        shots = [
            {"dur": 4.5, "hour": [6.6, 8.5], "weather": rain,
             "cam": {"around": "gino", "from": [4.5, 1.8, 0.5], "to": [12, 6, 1.0]},
             "captions": [{"text": "Good morning, Gino ☀️", "at": 2.0, "y": "bottom"}]},
            {"dur": 4.5, "hour": [10, 13], "weather": rain, "speed": 1.6,
             "cam": {"around": "home", "from": [32, 18, -1.1], "to": [27, 14, -0.4]},
             "captions": [{"text": say[0], "at": 0.3, "y": "bottom"}]},
            {"dur": 4.5, "hour": [14, 17], "weather": rain, "speed": 1.6,
             "cam": {"around": "gino", "from": [8, 3.5, -0.6], "to": [6, 2.6, 0.4]},
             "captions": [{"text": say[1], "at": 0.3, "y": "bottom"}]},
            {"dur": 5.5, "hour": [17.4, 22.5], "weather": rain,
             "cam": {"around": "home", "from": [26, 12, 0.2], "to": [34, 18, -0.5]},
             "captions": [{"text": say[2], "at": 0.3, "until": 2.8, "y": "bottom"},
                          {"text": "Goodnight, Gino 🌙", "at": 2.8, "y": "bottom"}]},
        ]
        what = " ".join(s.rstrip(".") + "." for s in lines[:2])
        text = f"A day in Gino's life 🌿 {what} He's an AI capybara who lives his own life, all on his own."
        title = "A day in Gino's life"

    shots.append({"dur": END_SECONDS, "hour": shots[-1]["hour"][1:] or shots[-1]["hour"],
                  "asleep": shots[-1].get("asleep", False), "weather": rain,
                  "cam": {**shots[-1]["cam"], "from": shots[-1]["cam"].get("to") or shots[-1]["cam"]["from"]}})
    caption = f"{text} Watch him live at {_end()[1].split(' · ')[-1]} {HASHTAGS}"
    caption = " ".join(caption.split())
    if public.check(caption):  # belt and braces: if anything slipped through, fall back to plain words
        caption = f"{KIND_NAMES[kind]} 🌿 Gino is an AI capybara who lives his own life. {HASHTAGS}"
    return {"kind": kind, "title": title, "caption": caption[:2000], "source": source,
            "fps": config.CLIP_FPS, "width": config.CLIP_SIZE[0], "height": config.CLIP_SIZE[1],
            "state": state, "shots": shots, "end": _end(), "end_seconds": END_SECONDS, "quality": 0.88,
            "render_scale": config.CLIP_RENDER_SCALE, "sounds": _sound_plan(shots)}


def _sound_plan(shots: list[dict]) -> list[list]:
    """Which of his meadow sounds plays when: [[track, start, end], ...]."""
    out, t = [], 0.0
    for s in shots:
        h0, h1 = s["hour"][0], (s["hour"][1:] or s["hour"])[0]
        mid = ((h0 + h1) / 2) % 24
        track = "rain" if s.get("weather") == "rain" else ("day" if 6.3 <= mid <= 19.3 else "night")
        if out and out[-1][0] == track:
            out[-1][2] = t + s["dur"]
        else:
            out.append([track, t, t + s["dur"]])
        t += s["dur"]
    return out


# ---------------------------------------------------------------- making one (in the background)

def make(kind: str = "", by: str = "auto", caption: str = "") -> int:
    """Start filming a clip in the background. Returns its id straight away (status 'making')."""
    if not available():
        raise RuntimeError("the video camera isn't set up on this server")
    if db.q("SELECT 1 FROM clips WHERE status='making' AND ts>?", (time.time() - config.CLIP_TIMEOUT - 60,)):
        raise RuntimeError("Gino is already filming a clip. One at a time!")
    kind = kind if kind in KINDS else best_kind()
    job = plan(kind)
    own = _clean(caption, 300)
    if own:  # Gino wrote his own words for it
        job["caption"] = f"{own} {HASHTAGS}"
    cid = db.x("INSERT INTO clips(ts,kind,title,caption,status,made_by,source,seconds,script) "
               "VALUES(?,?,?,?,?,?,?,?,?)",
               (time.time(), job["kind"], job["title"], job["caption"], "making", by, job["source"],
                sum(s["dur"] for s in job["shots"]), json.dumps(script(job), ensure_ascii=False)))
    threading.Thread(target=_film, args=(cid, job), daemon=True, name=f"clip-{cid}").start()
    return cid


def script(job: dict) -> dict:
    """The words on screen and when they appear (seconds from the start). Already public-safe: from plan()."""
    lines, t = [], 0.0
    for shot in job["shots"]:
        for c in shot.get("captions", []):
            lines.append({"text": c["text"], "at": round(t + c.get("at", 0), 2),
                          "until": round(t + c.get("until", shot["dur"]), 2)})
        t += shot["dur"]
    return {"seconds": round(t, 2), "lines": sorted(lines, key=lambda l: l["at"])}


def _film(cid: int, job: dict) -> None:
    CLIPS_DIR.mkdir(exist_ok=True)
    name = f"gino-{cid}-{job['kind']}.mp4"
    out = CLIPS_DIR / name
    started = time.time()
    progress[cid] = "waiting for the camera"
    with _busy, photo._lock:  # one browser at a time on the small server
        progress[cid] = "setting up the camera"
        try:
            p = subprocess.Popen([sys.executable, "-m", "gino.clips", "render", str(out)], stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=str(config.ROOT),
                                 env={**os.environ, "HOME": os.environ.get("TMPDIR", "/tmp")})
            p.stdin.write(json.dumps(job).encode()); p.stdin.close()
            timer = threading.Timer(config.CLIP_TIMEOUT, p.kill); timer.start()
            tail = []
            for raw in p.stderr:
                line = raw.decode(errors="replace").rstrip()
                if line.startswith("clip: frame "):
                    n, total = line.split()[2].split("/")
                    progress[cid] = f"filming frame {n} of {total}"
                else:
                    tail = (tail + [line])[-30:]
            p.wait(); timer.cancel()
            ok = p.returncode == 0 and out.exists() and out.stat().st_size > 10_000
        except Exception as e:  # noqa: BLE001
            ok, tail = False, [str(e)]
    progress.pop(cid, None)
    if ok:
        db.x("UPDATE clips SET status='ready', filename=? WHERE id=?", (name, cid))
        db.event("clip", f"filmed a {job['kind']} clip of his life in {int(time.time() - started)} s")
        log.info("Clip %s ready (%s, %.0f s to make)", cid, job["kind"], time.time() - started)
        _tidy()
        from . import tiktok
        tiktok.after_clip(cid)
    else:
        reason = "it took too long" if time.time() - started >= config.CLIP_TIMEOUT else "the camera didn't work"
        log.warning("Clip %s failed: %s", cid, "\n".join(tail)[-1500:])
        db.x("UPDATE clips SET status='failed', error=? WHERE id=?", (reason, cid))
        out.unlink(missing_ok=True)


def _tidy() -> None:
    for r in db.q("SELECT id, filename, polished FROM clips WHERE filename!='' ORDER BY id DESC LIMIT -1 OFFSET ?",
                  (KEEP,)):
        (CLIPS_DIR / r["filename"]).unlink(missing_ok=True)
        if r["polished"]:
            (CLIPS_DIR / r["polished"]).unlink(missing_ok=True)
        db.x("UPDATE clips SET filename='', polished='' WHERE id=?", (r["id"],))


def path(cid: int, raw: bool = False):
    """The clip's video: the polished one when dad's PC made one (unless raw=True), else the original."""
    rows = db.q("SELECT filename, polished FROM clips WHERE id=? AND status='ready' AND filename!=''", (cid,))
    if not rows:
        return None
    for name in ([] if raw else [rows[0]["polished"]]) + [rows[0]["filename"]]:
        if name and (CLIPS_DIR / name).exists():
            return CLIPS_DIR / name
    return None


# ---------------------------------------------------------------- polishing on dad's PC (FilmCraft)
# Dad's PC runs a small script (see deploy/README.md, "Polishing videos in FilmCraft") that asks for clips that
# haven't been polished, edits them in FilmCraft and sends the finished video back. When his PC is off, nothing
# waits for it: the clips just stay as they are.

POLISH_DAYS = 3        # only fresh clips are worth polishing
POLISHER_RECENT = 7200  # the polisher counts as "on" if it asked for work in the last 2 hours
MAX_POLISHED = 64_000_000


def polish_queue() -> list[dict]:
    db.put("polisher_seen", time.time())
    rows = db.q("SELECT id, kind, title, script FROM clips WHERE status='ready' AND filename!='' AND polished='' "
                "AND polish_note='' AND tiktok_status='' AND ts>? ORDER BY id DESC LIMIT 5",
                (time.time() - POLISH_DAYS * 86400,))
    out = []
    for r in rows:
        if path(r["id"], raw=True):
            try:
                r["script"] = json.loads(r["script"]) if r["script"] else None
            except ValueError:
                r["script"] = None
            out.append(r)
    return out


def polisher_on(now: float | None = None) -> bool:
    return (now or time.time()) - float(db.get("polisher_seen", 0) or 0) < POLISHER_RECENT


def save_polished(cid: int, data: bytes) -> str:
    """Keep the polished video dad's PC sent. Raises RuntimeError (in plain words) if it can't be used."""
    rows = db.q("SELECT kind, filename, tiktok_status FROM clips WHERE id=? AND status='ready'", (cid,))
    if not rows or not rows[0]["filename"]:
        raise RuntimeError("That clip isn't here any more.")
    if rows[0]["tiktok_status"] in ("sending", "sent", "posted"):
        raise RuntimeError("That clip has already gone to TikTok, so the polished one isn't needed.")
    if not 10_000 < len(data) <= MAX_POLISHED:
        raise RuntimeError("That video is the wrong size.")
    if data[4:8] != b"ftyp":
        raise RuntimeError("That isn't an MP4 video.")
    name = f"gino-{cid}-{rows[0]['kind']}-polished.mp4"
    tmp = CLIPS_DIR / (name + ".part")
    CLIPS_DIR.mkdir(exist_ok=True)
    tmp.write_bytes(data)
    os.replace(tmp, CLIPS_DIR / name)
    db.x("UPDATE clips SET polished=?, polish_note='' WHERE id=?", (name, cid))
    db.event("clip", "his clip got polished in FilmCraft on dad's computer")
    return "Thanks! Gino will use the polished version."


def polish_failed(cid: int, note: str) -> None:
    """The PC couldn't polish it: remember that so it isn't tried again and again."""
    db.x("UPDATE clips SET polish_note=? WHERE id=? AND polished=''", (("failed: " + " ".join(note.split()))[:300], cid))


def listing(limit: int = 30) -> list[dict]:
    rows = db.q("SELECT id,ts,kind,title,caption,status,seconds,error,made_by,tiktok_status,tiktok_note,tiktok_ts,"
                "polished FROM clips ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["progress"] = progress.get(r["id"], "")
        r["has_video"] = r["status"] == "ready" and path(r["id"]) is not None
        r["polished"] = bool(r["polished"]) and r["has_video"]
    return rows


def maybe_auto(now: float | None = None) -> None:
    """Called from his heartbeat: once a day (in the evening) he films a clip of his own."""
    if not available() or config.CLIPS_PER_DAY <= 0:
        return
    from .brain import local_now
    local = local_now()
    if local.hour < config.CLIP_HOUR:
        return
    start = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    done = db.q("SELECT COUNT(*) AS n FROM clips WHERE made_by='auto' AND ts>=?", (start,))[0]["n"]
    if done >= config.CLIPS_PER_DAY or db.q("SELECT 1 FROM clips WHERE status='making'"):
        return
    try:
        make(by="auto")
    except RuntimeError as e:
        log.info("No clip today: %s", e)


def context_lines() -> str:
    """What Gino knows about his clips (shown in his turn when the camera is on)."""
    if not available():
        return ""
    rows = db.q("SELECT title, tiktok_status FROM clips WHERE status='ready' ORDER BY id DESC LIMIT 3")
    if not rows:
        return "You have a video camera now: make_clip films a short video of your life for your TikTok."
    seen = "; ".join(r["title"] + (" (on TikTok)" if r["tiktok_status"] == "posted" else "") for r in rows)
    return f"Your latest videos: {seen}."


# ---------------------------------------------------------------- the browser side (separate process)

def _audio_args(sounds: list[list], total: float) -> tuple[list[str], str]:
    tracks = sorted({s[0] for s in sounds})
    args = []
    for tr in tracks:
        args += ["-stream_loop", "-1", "-i", str(SOUNDS / f"{tr}.mp3")]
    fadeover, parts = 1.0, []
    for i, (tr, a, b) in enumerate(sounds):
        end = b + (fadeover if i < len(sounds) - 1 else 0)
        inp = 1 + tracks.index(tr)
        parts.append(f"[{inp}:a]atrim=start={a:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[s{i}]")
    last = "s0"
    for i in range(1, len(sounds)):
        parts.append(f"[{last}][s{i}]acrossfade=d={fadeover}:c1=tri:c2=tri[x{i}]")
        last = f"x{i}"
    parts.append(f"[{last}]afade=t=in:d=0.6,afade=t=out:st={max(0, total - 1.8):.3f}:d=1.8,volume=0.9[aout]")
    return args, ";".join(parts)


def _render(job: dict, out: str) -> None:
    from playwright.sync_api import sync_playwright
    url = f"http://127.0.0.1:{config.PORT}/static/clip.html"
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"]
    total = sum(s["dur"] for s in job["shots"])
    audio_in, audio_filter = _audio_args(job["sounds"], total)
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "image2pipe", "-framerate", str(job["fps"]), "-c:v", "mjpeg", "-i", "-", *audio_in,
           "-filter_complex", audio_filter, "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-r", str(job["fps"]), "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.3f}", "-movflags", "+faststart",
           out + ".part.mp4"]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        with sync_playwright() as p:
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
            browser = p.chromium.launch(args=args, executable_path=config.PHOTO_CHROMIUM or None,
                                        proxy={"server": proxy, "bypass": "127.0.0.1,localhost"} if proxy else None)
            try:
                page = browser.new_page(viewport={"width": job["width"], "height": job["height"]},
                                        device_scale_factor=1, timezone_id=config.TIMEZONE or None)
                page.on("console", lambda m: print("page:", m.text, file=sys.stderr))
                local = os.environ.get("GINO_THREE_DIR")  # offline testing: three.js from a local copy
                if local:
                    page.route("https://cdn.jsdelivr.net/npm/three@*/**", lambda route: route.fulfill(
                        path=os.path.join(local, route.request.url.split("/", 5)[-1]),
                        content_type="text/javascript"))
                page.goto(url, wait_until="load", timeout=60_000)
                page.wait_for_function("window.clipReady === true", timeout=60_000)
                frames = page.evaluate("job => setupClip(job)", job)
                for i in range(frames):
                    data = page.evaluate("clipFrame()")
                    enc.stdin.write(base64.b64decode(data.split(",", 1)[1]))
                    if i % 24 == 0 or i == frames - 1:
                        print(f"clip: frame {i + 1}/{frames}", file=sys.stderr, flush=True)
            finally:
                browser.close()
        enc.stdin.close()
        if enc.wait(timeout=300) != 0:
            raise RuntimeError("ffmpeg failed")
        os.replace(out + ".part.mp4", out)
    finally:
        if enc.poll() is None:
            enc.kill()
        if os.path.exists(out + ".part.mp4"):
            os.unlink(out + ".part.mp4")


if __name__ == "__main__":
    if sys.argv[1:2] == ["render"]:
        _render(json.loads(sys.stdin.read()), sys.argv[2])
    elif sys.argv[1:2] == ["test"]:  # `python -m gino.clips test [kind] [out.mp4]` films one clip, posts nothing
        logging.basicConfig(level=logging.INFO)
        kind = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] in KINDS else best_kind()
        target = sys.argv[3] if len(sys.argv) > 3 else f"gino-clip-test-{kind}.mp4"
        if not available():
            sys.exit("No clip: the video camera isn't set up (gino clips on).")
        job = plan(kind)
        t0 = time.time()
        p = subprocess.run([sys.executable, "-m", "gino.clips", "render", os.path.abspath(target)],
                           input=json.dumps(job).encode(), cwd=str(config.ROOT))
        if p.returncode:
            sys.exit("No clip: the camera didn't work this time.")
        print(f"Saved '{job['title']}' ({job['kind']}) to {target} in {time.time() - t0:.0f} s. Nothing was posted.")
        print(f"Caption: {job['caption']}")
    else:
        print("usage: python -m gino.clips test [day|night|dream|made] [out.mp4]")
