"""Gino's video camera: short vertical clips of his life (9:16, about 20 seconds, with his meadow's sounds).

Made for TikTok, Reels and Shorts. The server films his real 3D world in a headless Chromium
(static/clip.html), one frame at a time, and ffmpeg turns the frames and his day/night/rain sounds into an MP4.
No AI image or video generation and no AI call, so a clip costs nothing from his daily budget (it only uses
the server's computer for a few minutes).

Seven kinds of clip, each a little story told from his own records:
  day     "A day in Gino's life": morning to night in 20 seconds, with things he did today
  night   "What Gino does while you sleep": a night timelapse, then he wakes up
  dream   he sleeps, dreams, and then the painting he made of the dream appears
  made    the newest thing he built or painted, and the story behind it
  cute    "Cute moments": quick cuts of him sitting, rolling, stretching, dancing, soaking in his pond, napping...
  tour    "Home tour": he shows you round his favourite things, one by one, with the stories behind them
  grow    "Watch my home grow": his meadow starts empty and everything he built pops up in the order he made it

Privacy: every word that goes into a clip or its caption goes through public.check(), the same filter as his
public website, and only drawings he already put on a public page are shown. Nothing from chats, memories or
journals. Dad sees the finished clips on his private page and decides what to post (see tiktok.py).

Off by default (GINO_CLIPS=0). `gino clips on` installs what it needs on the server.
"""
import base64
import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time

from . import config, db, keepsakes, live, photo, public, vitals

log = logging.getLogger("gino.clips")
KINDS = ("day", "night", "dream", "made", "cute", "tour", "grow")
KIND_NAMES = {"day": "A day in Gino's life", "night": "While you sleep", "dream": "A dream, then a painting",
              "made": "Something he made", "cute": "Cute moments", "tour": "Home tour",
              "grow": "Watch my home grow"}
EVERYDAY = ("day", "cute", "night", "tour", "grow")  # on days with no fresh dream or new thing, these take turns
FLAT_THINGS = ("path", "pond", "bridge")  # not worth a stop on a home tour
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
      script TEXT NOT NULL DEFAULT '', polished TEXT NOT NULL DEFAULT '', polish_note TEXT NOT NULL DEFAULT '',
      polished_by TEXT NOT NULL DEFAULT '')""")
    have = {r["name"] for r in db.q("PRAGMA table_info(clips)")}
    # script: the captions and when they show (for the polisher); polished: the finished version's file name;
    # polished_by: who finished it ('pc' = FilmCraft on dad's PC, 'server' = polish.py)
    for col in ("script", "polished", "polish_note", "polished_by"):
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
    # an ordinary day: take turns between the everyday stories (skipping the ones his home can't fill yet, and the
    # one he filmed last, so his videos don't all look the same)
    things = db.q("SELECT kind FROM habitat")
    ok = [k for k in EVERYDAY if (k != "tour" or sum(1 for t in things if t["kind"] not in FLAT_THINGS) >= 3)
          and (k != "grow" or len(things) >= 5)]
    last = db.q("SELECT kind FROM clips WHERE status!='failed' ORDER BY id DESC LIMIT 1")
    ok = [k for k in ok if not last or k != last[0]["kind"]] or ok
    return ok[int(now // 86400) % len(ok)]


# ---------------------------------------------------------------- the script for one clip

def _end() -> list[str]:
    site = re.sub(r"^https?://", "", config.PUBLIC_URL or "").rstrip("/") or "ginothecapybara.com"
    return ["Gino the capybara 🌿", f"An AI capybara living his own life · {site}"]


# ---- close-ups: every clip opens on his face, cuts back to it between scenes and ends zooming into it
FACE = [1.75, 0.22, 0.22]  # distance, height and angle of the close-up (angle 0: straight in front of his face)
END_SHOT = 4.0             # the closing zoom into his face; the name card shows for its last END_SECONDS
NOT_CARRIED = ("pond", "path", "bridge", "garden", "house", "fountain", "windmill", "tent", "pumpkins")
GRID = (16, 10)            # his meadow, in squares (as in static/world.js)


def _say(text: str, at: float = 0.3, until: float | None = None) -> dict:
    """Words in a speech bubble beside his face, as if he's saying them."""
    c = {"text": text, "at": at, "style": "speech"}
    if until is not None:
        c["until"] = until
    return c


def _face(dur: float, hour: list, *, frm=None, to=None, say: list | None = None, mood: str = "", pet: bool = False,
          asleep: bool = False, weather=None, **extra) -> dict:
    """A close-up of his face (the camera stays in front of it even if he turns)."""
    shot = {"dur": dur, "hour": hour, "weather": weather, "asleep": asleep, "face": True,
            "cam": {"around": "face", "track": True, "from": list(frm or FACE), "to": list(to or frm or FACE)},
            "captions": list(say or []), **extra}
    if mood:
        shot["emotion"] = mood
    if pet:
        shot["pet"] = True
    if not asleep and "pose" not in extra and "go" not in extra:
        shot["pose"] = "idle"
    return shot


def _opener(hour: list, say: str = "", **kw) -> dict:
    """Open on his face, then pull back to show where he is."""
    return _face(2.8, hour, frm=FACE, to=[6.5, 2.4, 0.6], say=[_say(say, 0.25, 2.3)] if say else [], **kw)


def _react(prev: dict, say: str = "", mood: str = "happy", pet: bool = True, dur: float = 1.6) -> dict:
    """A quick cut to his face between scenes: a blink, a happy hop, his mood above his head."""
    h = (prev["hour"][1:] or prev["hour"])[0]
    asleep = bool(prev.get("asleep"))
    return _face(dur, [h, h + 0.15], frm=[2.4, 0.4, -0.75], to=[2.0, 0.3, -0.55],
                 say=[_say(say, 0.15)] if say else [], mood="" if asleep else mood, pet=pet and not asleep,
                 asleep=asleep, weather=prev.get("weather"), tint=prev.get("tint"))


def _ending(prev: dict, say: str = "", mood: str = "proud", hour: list | None = None) -> dict:
    """End on a slow zoom into his (proud) face: it lands on the same close-up the clip opened with, so it loops."""
    h = (prev["hour"][1:] or prev["hour"])[0]
    return _face(END_SHOT, hour or [h, h + 0.4], frm=[6, 2.0, 0.55], to=FACE, mood=mood, weather=prev.get("weather"),
                 say=[_say(say, 0.15, END_SHOT - END_SECONDS)] if say else [])


def _follow(dur: float, hour: list, item: dict | None, captions: list, weather=None, act: str = "look", **extra) -> dict:
    """The camera tags along behind him as he trots over to one of his things."""
    shot = {"dur": dur, "hour": hour, "weather": weather, "captions": captions,
            "cam": {"around": "gino", "track": True, "from": [4.2, 2.1, 3.0], "to": [5.2, 2.6, 2.75]}, **extra}
    if item:
        shot["go"] = {"id": item["id"], "act": act, "near": 1.0 + 0.9 * float(item.get("size") or 1)}
    return shot


def _favourite(state: dict, kinds: tuple = ()) -> dict | None:
    """Something of his to walk over to: one of `kinds` if he has one, else the newest thing he built."""
    things = [it for it in state.get("habitat") or [] if it.get("kind") not in ("path", "pond", "bridge")]
    pick = [it for it in things if it.get("kind") in kinds] or things
    return max(pick, key=lambda it: it["id"]) if pick else None


def _carry_spots(item: dict, state: dict) -> dict | None:
    """For a new thing he built: a free square a little way off where it 'starts', and where Gino stands, so in
    the clip he walks over, lifts it onto his back and carries it to its real spot."""
    if (item.get("kind") or "") in NOT_CARRIED:
        return None
    ix, iy = item["x"], item["y"]
    px, py = (state.get("pos") or [7, 5])[:2]
    taken = {(it["x"], it["y"]) for it in state.get("habitat") or []}
    base = math.atan2(py - iy, px - ix) if (px, py) != (ix, iy) else math.pi
    for turn in (0, 0.6, -0.6, 1.2, -1.2, 1.9, -1.9, math.pi):
        a = base + turn
        dx, dy = math.cos(a), math.sin(a)
        fx, fy = round(ix + dx * 2.6), round(iy + dy * 2.6)
        sx, sy = ix + dx * 5.2, iy + dy * 5.2
        if (0 <= fx < GRID[0] and 0 <= fy < GRID[1] and (fx, fy) not in taken
                and 0 <= sx <= GRID[0] - 1 and 0 <= sy <= GRID[1] - 1):
            return {"carry": {"id": item["id"], "from": [fx, fy], "to": [ix, iy]},
                    "start": {"at": [round(sx, 2), round(sy, 2)], "facing": [fx, fy]}}
    return None


# "cute" clips: little moments, in a different order each day. Acts are the ones he does in static/world.js.
# (act, words, mood, cute pose): the cute poses are the ones he strikes in static/world.js (_debug.cutePose)
CUTE_FREE = [("sit", "Sitting pretty 🌼", "content", "sit"), ("roll", "Belly up! 🙃", "happy", "roll"),
             ("stretch", "A big, big stretch 🙆", "proud", "stretch"), ("dance", "Dance break! 💃", "excited", "dance"),
             ("hops", "Happy hops! 💛", "excited", "hop"), ("nap", "Just resting my eyes… 💤", "sleepy", "curl"),
             ("orange", "Balancing act 🍊", "calm", "orange")]
CUTE_AT = [("swim", "Spa day 🍊", "relaxed", ("pond",)),
           ("sniff", "Sniff sniff 🌷", "curious", ("flowers", "bush", "mushroom")),
           ("sit", "My favourite spot 🪑", "content", ("bench", "picnic", "campfire")),
           ("dance", "Music time 🎹", "excited", ("piano",))]
BIG_NEAR = {"house": 1.0, "tent": 0.8, "fountain": 0.7, "garden": 0.7, "picnic": 0.5, "windmill": 0.6,
            "gallery": 0.6, "bed": 0.4, "piano": 0.4, "pumpkins": 0.3, "campfire": 0.3}


def _near(it: dict) -> float:
    """How far from one of his things Gino stands so he's beside it, not inside it."""
    return round(1.2 + 0.6 * float(it.get("size") or 1) + BIG_NEAR.get(it.get("kind") or "", 0), 2)


def _tour_stops(state: dict) -> list[dict]:
    """Up to four of his things for a home tour: ones with a story first, then the newest. Words already filtered."""
    things = [it for it in state.get("habitat") or [] if it.get("kind") not in FLAT_THINGS]
    things.sort(key=lambda it: (not it.get("story"), -it["id"]))
    out = []
    for it in things[:4]:
        story = it.get("story") if it.get("story") and it["story"] != keepsakes.PRIVATE_STORY else ""
        out.append({"id": it["id"], "x": it["x"], "y": it["y"], "kind": it.get("kind") or "",
                    "size": min(2.5, max(0.4, float(it.get("size") or 1))), "emoji": _clean(it.get("emoji"), 8),
                    "name": _clean(it.get("name"), 40) or "thing", "story": _clean(story, 110),
                    "description": _clean(it.get("description"), 90)})
    return out


def plan(kind: str, now: float | None = None) -> dict:
    """The shots, captions and the post's text for one clip. Everything in it is safe for the whole world."""
    now = now or time.time()
    state = photo.scene_state()
    state["habitat"] = live.build()["habitat"]  # names and stories already filtered for visitors (fresh, not cached)
    rain = "rain" if (state.get("weather") or {}).get("kind") == "rain" else None
    since = now - 86400
    built, art = _built(since), _public_art(since)
    lines = [f"He built a {b['name']} {b['emoji']}".strip() for b in built[:2]]
    lines += [f"He painted '{a['title']}' 🎨" for a in art[:1]]
    note = _clean(live._diary_line(), 90)
    source, art_url, title = "", "", KIND_NAMES.get(kind, "")
    easel = _favourite(state, ("easel", "gallery"))
    extra: dict = {}

    if kind == "dream":
        pics = [a for a in _public_art(now - 7 * 86400, dream=True) if not _already(f"art:{a['id']}")] or \
            _public_art(dream=True)
        if not pics:
            kind = "night"
        else:
            p = pics[0]
            source, art_url = f"art:{p['id']}", f"/blog/art/{p['id']}.svg"
            sleep = _face(3.2, [23.2, 23.8], frm=FACE, to=[6, 2.6, 0.7], asleep=True, tint=0.5, weather=rain,
                          captions=[{"text": "Shh… Gino is asleep 💤", "at": 1.0, "y": "bottom"}])
            dreaming = {"dur": 4.8, "hour": [1.5, 2.5], "asleep": True, "tint": 1.0, "weather": rain,
                        "cam": {"around": "gino", "from": [4.4, 1.6, 0.2], "to": [3.6, 1.4, -0.2]},
                        "captions": [{"text": "…and he's dreaming 🌙", "at": 0.4, "y": "bottom"}]}
            woke = _face(1.8, [7.2, 7.4], frm=[2.3, 0.35, -0.35], to=[1.9, 0.25, -0.2], mood="excited", pet=True,
                         say=[_say("I dreamed something! ✨", 0.15)], weather=rain)
            walk = _follow(3.0, [7.4, 7.9], easel, [{"text": "In the morning, he painted it:", "at": 0.3,
                                                     "y": "bottom"}], weather=rain, act="look")
            paint_it = {"dur": 5.8, "hour": [7.9, 8.6], "asleep": False, "activity": "painting", "pose": "look",
                        "cam": {"around": "gino", "from": [7, 3, -0.4], "to": [9, 4, -0.7]}, "art": art_url,
                        "weather": rain, "captions": [{"text": f"'{p['title']}'", "at": 1.0, "y": "bottom"}]}
            shots = [sleep, dreaming, woke, walk, paint_it, _ending(paint_it, "I painted my dream 🥹")]
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
            built_line = f"He built a {item['name']} {item['emoji']}".strip()
            moves = _carry_spots(item, state)
            opener = _opener([10, 10.5], "I had an idea… 💡", mood="curious", weather=rain)
            if moves:  # he carries it to its spot: follow him there, then watch up close as he lifts and sets it down
                extra = moves
                fetch = {"dur": 3.0, "hour": [10.5, 11.2], "weather": rain, "carry": True,
                         "cam": {"around": "gino", "track": True, "from": [4.2, 2.1, 3.0], "to": [4.6, 2.3, 2.6]},
                         "captions": [{"text": built_line, "at": 0.3, "y": "bottom"}]}
                carry = {"dur": 5.6, "hour": [11.2, 12.4], "weather": rain,
                         "cam": {"around": "gino", "track": True, "from": [4.6, 2.3, 1.25], "to": [4.0, 2.0, 0.95]},
                         "captions": [_say("Heave-ho! 💪", 0.2, 2.4), _say("Just a little further…", 2.6)]}
                middle = [fetch, carry]
            else:  # too big to carry: follow him over to it
                middle = [_follow(4.2, [10.5, 11.5], {**item, "size": 1.2}, [{"text": built_line, "at": 0.3,
                                                                              "y": "bottom"}], weather=rain),
                          {"dur": 4.0, "hour": [11.5, 12.4], "weather": rain, "pose": "look",
                           "cam": {"around": spot, "from": [7, 3.4, 0.6], "to": [5.5, 2.6, 1.1]},
                           "captions": [_say("Look what I made!", 0.3)]}]
            there = _react(middle[-1], "There! ✨", mood="proud")
            show = {"dur": 4.4, "hour": [13, 15], "weather": rain, "pose": "look",
                    "cam": {"around": spot, "from": [9, 5, 0.3], "to": [6, 3, 1.1]},
                    "captions": [{"text": story, "at": 0.3, "y": "bottom"}]}
            shots = [opener, *middle, there, show, _ending({**show, "hour": [17.2, 17.4]}, "I'm so proud of it 🥹")]
            why = f"In his words: “{item['story']}”" if item["story"] else "Nobody asked him to."
            text = (f"Gino built a {item['name']} {item['emoji']} today. {why} "
                    "He's an AI capybara who decides everything himself.")
            title = f"Gino built a {item['name']}"
        elif pic:
            source, art_url = f"art:{pic['id']}", f"/blog/art/{pic['id']}.svg"
            opener = _opener([9.5, 10], "I feel like painting today 🎨", mood="inspired", weather=rain)
            walk = _follow(3.2, [10, 10.8], easel, [{"text": "Gino felt like painting today 🎨", "at": 0.3,
                                                     "y": "bottom"}], weather=rain)
            painted = {"dur": 5.8, "hour": [11, 12], "weather": rain, "art": art_url, "pose": "look",
                       "activity": "painting", "cam": {"around": "gino", "from": [6, 2.6, 0.6], "to": [7, 3, 0.1]},
                       "captions": [{"text": f"'{pic['title']}'", "at": 1.2, "y": "bottom"}]}
            like = _react(painted, "Do you like it? 🥺", mood="hopeful")
            wide = {"dur": 3.6, "hour": [17.4, 18.2], "weather": rain,
                    "cam": {"around": "home", "from": [26, 13, -0.3], "to": [30, 16, -0.8]},
                    "captions": [{"text": "Nobody asked him to. He just wanted to.", "at": 0.4, "y": "bottom"}]}
            shots = [opener, walk, painted, like, wide, _ending(wide, "I made that! 🥹")]
            text = f"Gino painted '{pic['title']}' today 🎨 He's an AI capybara who makes art when he feels like it."
            title = f"Gino painted '{pic['title']}'"
        else:
            kind = "day"

    if kind == "tour":
        stops = _tour_stops(state)
        if len(stops) < 3:
            kind = "cute"
        else:
            hello = _opener([9.5, 10], "Welcome to my home! 🏡", mood="happy", weather=rain)
            wide = {"dur": 3.0, "hour": [10, 10.6], "weather": rain,
                    "cam": {"around": "home", "from": [32, 18, -0.9], "to": [27, 15, -0.5]},
                    "captions": [{"text": "Everything here, he built himself", "at": 0.3, "y": "bottom"}]}
            shown, h = [], 10.8
            for i, it in enumerate(stops):
                ang = (-0.5, 0.6, -1.0, 0.3)[i % 4]
                about = it["story"] or it["description"]
                caps = [_say(f"This is my {it['name']} {it['emoji']}".strip(), 0.2, 2.0)]
                if about:
                    caps.append({"text": f"“{about}”" if it["story"] else about, "at": 1.9, "y": "bottom"})
                shown.append({"dur": 3.8, "hour": [h, h + 0.9], "weather": rain, "pose": "look",
                              "near": {"id": it["id"], "dist": _near(it), "side": ang + 0.95},
                              "cam": {"around": [it["x"], it["y"]], "from": [6.4 + it["size"], 3.0, ang],
                                      "to": [5.2 + it["size"], 2.4, ang + 0.35]},
                              "captions": caps})
                h += 1.6
            shots = [hello, wide, *shown[:2], _react(shown[1], "Isn't it cosy? 🥰", mood="proud"), *shown[2:],
                     _ending(shown[-1], "Come back and visit soon! 💛", mood="happy")]
            names = ", ".join(f"{it['name']} {it['emoji']}".strip() for it in stops[:3])
            text = (f"A little tour of Gino's home 🏡 His {names}, and the stories behind them. "
                    "He's an AI capybara who builds his own world, piece by piece.")
            title = "A tour of Gino's home"

    if kind == "grow":
        rows = db.q("SELECT id, ts FROM habitat ORDER BY id")
        if len(rows) < 5:
            kind = "cute"
        else:
            born = float(vitals.load().get("born") or rows[0]["ts"])
            day_of = [max(1, int((r["ts"] - born) // 86400) + 1) for r in rows]
            extra = {"grow": {"order": {str(r["id"]): i for i, r in enumerate(rows)},
                              "labels": [f"Day {d}" for d in day_of]}}
            empty = {"dur": 2.6, "hour": [8.5, 9], "weather": rain, "grown": 0,
                     "cam": {"around": "home", "from": [30, 17, -0.5], "to": [28, 16, -0.6]},
                     "captions": [{"text": "Day 1: just grass 🌱", "at": 0.3, "y": "bottom"}]}
            grow = {"dur": 9.0, "hour": [9, 17], "weather": rain, "grow": True,
                    "cam": {"around": "home", "from": [28, 16, -0.6], "to": [24, 13, 0.7]},
                    "captions": [{"text": "Then he started building…", "at": 0.3, "until": 3.6, "y": "bottom"},
                                 {"text": f"{len(rows)} things, all his own idea ✨", "at": 5.6, "y": "bottom"}]}
            shots = [_opener([8, 8.5], "My home didn't always look like this… 🌱", mood="thoughtful",
                             weather=rain, grown=0),
                     empty, grow, _react(grow, "I made all this! 🥹", mood="proud"),
                     _ending({**grow, "hour": [17.4, 17.6]}, "Home sweet home 🏡")]
            text = (f"Watch Gino's home grow 🌱➡️🏡 It started as an empty meadow. Over {day_of[-1]} days he built "
                    f"{len(rows)} things, every one his own idea. He's an AI capybara who makes his own world.")
            title = "Watch my home grow"

    if kind == "cute":
        rng = random.Random(int(now // 86400))
        pool = [(act, cap, mood, None, cute) for act, cap, mood, cute in CUTE_FREE]
        for act, cap, mood, kinds in CUTE_AT:
            mine = [it for it in state.get("habitat") or [] if it.get("kind") in kinds]
            if mine:
                pool.append((act, cap, mood, rng.choice(mine), ""))
        rng.shuffle(pool)
        # the ones you can't miss come first: a belly-up roll, and a soak in his pond (or happy hops)
        must = [m for m in pool if m[0] == "roll"][:1] + ([m for m in pool if m[0] == "swim"] or
                                                          [m for m in pool if m[0] == "orange"])[:1]
        picks = list(must)
        for m in pool:  # then a few more, each a different thing to do
            if len(picks) < 5 and m[0] not in {x[0] for x in picks}:
                picks.append(m)
        rng.shuffle(picks)
        picks.sort(key=lambda m: m[0] == "swim")  # the pond soak comes last, so he isn't left standing in the water
        moments, h = [], 9.0
        for i, (act, cap, mood, it, cute) in enumerate(picks):
            ang = (0.35, -0.4, 0.6, -0.7, 0.2)[i % 5]
            shot = {"dur": 2.6, "hour": [h, h + 0.5], "weather": rain, "pose": act, "emotion": mood,
                    "cam": {"around": "gino", "from": [4.8, 1.7, ang], "to": [4.0, 1.4, ang + 0.25]},
                    "captions": [{"text": cap, "at": 0.2, "y": "bottom"}]}
            if cute:  # he turns to the camera and strikes the pose
                shot["cute"] = cute
            if it:  # he does it at one of his things: he's beside it (or in the pond), and the camera sees both
                shot["near"] = {"id": it["id"], "dist": 0 if act == "swim" else _near(it),
                                "side": rng.uniform(0, 6.28)}
                shot["cam"] = {"around": "gino", "from": [5.4, 2.0, 1.15], "to": [4.6, 1.7, 1.35]}
            moments.append(shot)
            h += 1.6
        hi = _opener([8.5, 9], "Wanna see something cute? 🥺", mood="happy", weather=rain)
        hop = _react(moments[1], "Hehe! 💛", mood="happy", dur=1.8)
        shots = [hi, *moments[:2], hop, *moments[2:], _ending({**moments[-1], "hour": [17, 17.3]}, "Bye-bye! 👋",
                                                                 mood="happy")]
        text = ("Cute moments with Gino 🥺💛 Sitting, rolling, stretching and dancing, whenever he feels like it. "
                "He's an AI capybara who lives his own life, all on his own.")
        title = "Cute moments with Gino"

    if kind == "night":
        bed = _opener([20.5, 21], "Time for bed… 🥱", mood="sleepy", weather=rain)
        wide = {"dur": 3.4, "hour": [21, 22.6], "weather": rain,
                "cam": {"around": "home", "from": [30, 16, -0.4], "to": [24, 12, -0.9]},
                "captions": [{"text": "You go to bed… 🌙", "at": 0.6, "y": "bottom"}]}
        night = {"dur": 5.2, "hour": [23, 28.5], "asleep": True, "tint": 0.5, "weather": rain, "speed": 1.6,
                 "cam": {"around": "gino", "from": [9, 5, 1.4], "to": [5, 2.4, 0.4]},
                 "captions": [{"text": "Gino curls up under the stars ✨", "at": 0.5, "until": 2.8, "y": "bottom"},
                              {"text": (f"Tonight's dream: '{art[0]['title']}'" if art and art[0].get('dream_id')
                                        else "He dreams about his day"), "at": 2.8, "y": "bottom"}]}
        snooze = _react(night, "zzz… 💤", dur=1.6)
        wake = _face(3.6, [6.4, 7.6], frm=[2.0, 0.3, 0.3], to=[5, 1.8, 0.8], activity="having a big stretch",
                     pose="stretch", mood="happy", weather=rain,
                     captions=[{"text": "…and wakes up ready for a new day ☀️", "at": 0.6, "y": "bottom"}])
        off = _follow(3.0, [7.6, 8.4], _favourite(state), [], weather=rain)
        shots = [bed, wide, night, snooze, wake, off, _ending(off, "Good morning! ☀️", mood="happy")]
        text = ("What Gino does while you sleep 🌙 He's an AI capybara who lives in his own little world, "
                "day and night, even when nobody's watching.")
        title = "What Gino does while you sleep"

    if kind == "day":
        extra_lines = lines + ([note] if note else []) + ([_feeling(state)] if _feeling(state) else [])
        say = (extra_lines + ["He decides everything himself", "Snack time 🍉", "Just vibing 🌿"])[:3]
        hello = _opener([6.6, 7.2], "Good morning! ☀️", mood="happy", weather=rain)
        trot = _follow(3.6, [8, 10.5], _favourite(state), [{"text": say[0], "at": 0.3, "y": "bottom"}],
                       weather=rain, speed=1.4)
        wide = {"dur": 3.6, "hour": [11, 14], "weather": rain, "speed": 1.6, "pose": "graze",
                "cam": {"around": "home", "from": [32, 18, -1.1], "to": [27, 14, -0.4]},
                "captions": [{"text": say[1], "at": 0.3, "y": "bottom"}]}
        vibe = _react(wide, "This is the life 🌿", mood="content")
        evening = {"dur": 4.2, "hour": [16.5, 19.5], "weather": rain, "speed": 1.4, "pose": "sit",
                   "cam": {"around": "gino", "from": [8, 3.5, -0.6], "to": [6, 2.6, 0.4]},
                   "captions": [{"text": say[2], "at": 0.3, "y": "bottom"}]}
        shots = [hello, trot, wide, vibe, evening, _ending(evening, "Goodnight! 🌙", mood="happy")]
        what = " ".join(s.rstrip(".") + "." for s in lines[:2])
        text = f"A day in Gino's life 🌿 {what} He's an AI capybara who lives his own life, all on his own."
        title = "A day in Gino's life"

    for shot in shots:  # every bubble and caption is checked again, just in case
        shot["captions"] = [c for c in shot.get("captions", []) if c["text"] and not public.check(c["text"])]
    caption = f"{text} Watch him live at {_end()[1].split(' · ')[-1]} {HASHTAGS}"
    caption = " ".join(caption.split())
    if public.check(caption):  # belt and braces: if anything slipped through, fall back to plain words
        caption = f"{KIND_NAMES[kind]} 🌿 Gino is an AI capybara who lives his own life. {HASHTAGS}"
    return {"kind": kind, "title": title, "caption": caption[:2000], "source": source,
            "fps": config.CLIP_FPS, "width": config.CLIP_SIZE[0], "height": config.CLIP_SIZE[1],
            "state": state, "shots": shots, "end": _end(), "end_seconds": END_SECONDS, "quality": 0.88,
            "render_scale": config.CLIP_RENDER_SCALE, "sounds": _sound_plan(shots), **extra}


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
            line = {"text": c["text"], "at": round(t + c.get("at", 0), 2),
                    "until": round(t + c.get("until", shot["dur"]), 2)}
            if c.get("style") == "speech":
                line["speech"] = True  # said by Gino in a bubble beside his face
            lines.append(line)
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
        from . import polish
        polish.maybe_polish()
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
# haven't been polished, edits them in FilmCraft and sends the finished video back. Dad chooses who polishes with
# `gino polish pc|server|off`; in "pc" mode the server (polish.py) steps in when his PC is off or slow.

POLISH_DAYS = 3        # only fresh clips are worth polishing
POLISHER_RECENT = 7200  # the polisher counts as "on" if it asked for work in the last 2 hours
MAX_POLISHED = 64_000_000


def polish_queue() -> list[dict]:
    db.put("polisher_seen", time.time())
    if config.POLISHER != "pc":  # dad chose the server's polish (or none): the PC has nothing to do
        return []
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
    old = db.q("SELECT polished FROM clips WHERE id=?", (cid,))[0]["polished"]
    db.x("UPDATE clips SET polished=?, polished_by='pc', polish_note='' WHERE id=?", (name, cid))
    if old and old != name:  # FilmCraft's version replaces the server's
        (CLIPS_DIR / old).unlink(missing_ok=True)
    db.event("clip", "his clip got polished in FilmCraft on dad's computer")
    return "Thanks! Gino will use the polished version."


def polish_failed(cid: int, note: str) -> None:
    """The PC couldn't polish it: remember that so it isn't tried again and again."""
    db.x("UPDATE clips SET polish_note=? WHERE id=? AND polished=''", (("failed: " + " ".join(note.split()))[:300], cid))


def listing(limit: int = 30) -> list[dict]:
    rows = db.q("SELECT id,ts,kind,title,caption,status,seconds,error,made_by,tiktok_status,tiktok_note,tiktok_ts,"
                "polished,polished_by,polish_note FROM clips ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["progress"] = progress.get(r["id"], "")
        r["has_video"] = r["status"] == "ready" and path(r["id"]) is not None
        r["polished"] = bool(r["polished"]) and r["has_video"]
        r["polished_by"] = (r["polished_by"] or "pc") if r["polished"] else ""
        r["polishing"] = r.pop("polish_note") == "server: polishing"
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
        print(f"usage: python -m gino.clips test [{'|'.join(KINDS)}] [out.mp4]")
