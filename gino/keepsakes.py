"""A home that remembers: things in Gino's world can carry the story of why they're there.

When something meaningful happens (a passion that lasts, a goal reached, a memory he treasures, the time of day
dad usually comes to visit), Gino may build something that marks it and give it a story. Anyone watching him at
/live can click it and read that story, so over time his meadow becomes a picture of his life.

Nothing here costs money: it only notices meaningful things in his own records and, now and then, mentions one in
his turn. He decides whether to build anything at all.
"""
import datetime as dt
import random
import re
import time

from . import config, continuity, db, public

DAY = 86400
GRID_W, GRID_H = 16, 10

# How a keepsake's story looks on the public page when Gino's own words can't be shown there.
PRIVATE_STORY = "Gino keeps the story of this one to himself."


def free_spot(x: int, y: int) -> tuple[int, int] | None:
    """The free square nearest to (x, y), or None if the meadow is full."""
    taken = {(r["x"], r["y"]) for r in db.q("SELECT x,y FROM habitat")}
    cells = [(cx, cy) for cy in range(GRID_H) for cx in range(GRID_W) if (cx, cy) not in taken]
    if not cells:
        return None
    return min(cells, key=lambda c: (abs(c[0] - x) + abs(c[1] - y), c[1], c[0]))


def place(name: str, emoji: str, x: int, y: int, kind: str = "", color: str = "", size: float = 1.0,
          description: str = "", story: str = "", origin: str = "") -> tuple[int, int, int] | None:
    """Put something in his world at (or near) x,y. Returns (item id, x, y), or None if there's no room."""
    spot = free_spot(x, y)
    if not spot:
        return None
    iid = db.x("INSERT INTO habitat(ts,name,emoji,x,y,description,kind,color,size,story,origin) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (time.time(), name[:40], emoji[:4] or "✨", spot[0], spot[1], description[:300], kind, color,
                max(0.5, min(size, 2.5)), story[:1500], origin[:40]))
    return iid, spot[0], spot[1]


# ---------------------------------------------------------------- noticing what matters

def _local(ts: float) -> dt.datetime:
    from .brain import tz  # late import: brain imports this module
    return dt.datetime.fromtimestamp(ts, tz())


def visit_pattern(now: float | None = None) -> dict | None:
    """The part of the day dad usually turns up, if there is a clear habit (several days, mostly one time of day)."""
    now = now or time.time()
    parts = {"morning": range(5, 12), "afternoon": range(12, 18), "evening": range(18, 23)}
    days: dict[str, set] = {k: set() for k in (*parts, "night")}
    for r in db.q("SELECT ts FROM chat WHERE sender='dad' AND ts>?", (now - 30 * DAY,)):
        t = _local(r["ts"])
        part = next((k for k, hours in parts.items() if t.hour in hours), "night")
        days[part].add(t.date())
    total = sum(len(v) for v in days.values())
    if not total:
        return None
    part, seen = max(days.items(), key=lambda kv: len(kv[1]))
    if len(seen) >= 3 and len(seen) / total >= 0.6:
        return {"part": part, "days": len(seen)}
    return None


def _marked(words: str, items: list[dict]) -> bool:
    w = words.lower()
    return any(w in f"{i['name']} {i['story']}".lower() for i in items)


def candidates(now: float | None = None) -> list[tuple[str, str]]:
    """Meaningful things in his life that his home doesn't show yet, as (key, words for Gino)."""
    now = now or time.time()
    items = db.q("SELECT name,story FROM habitat")
    out = []
    for t in continuity.interests(now):
        if t["n_days"] >= 3 and not _marked(t["topic"], items):
            out.append((f"interest:{t['topic']}", f"Your love of {t['topic']} has lasted {t['n_days']} different "
                                                  "days now. It's part of who you are."))
    v = visit_pattern(now)
    if v:
        out.append((f"visits:{v['part']}", f"{config.DAD_NAME} mostly comes to see you in the {v['part']} "
                                           f"(on {v['days']} different days lately). That's become your time together."))
    for g in db.q("SELECT id,title FROM goals WHERE status='done' AND updated>? ORDER BY updated DESC LIMIT 3",
                  (now - 14 * DAY,)):
        out.append((f"goal:{g['id']}", f"You did it: \"{g['title']}\". Something that took real work."))
    for m in db.q("SELECT id,text FROM memories WHERE importance>=4 AND ts<? AND ts>? AND tags NOT LIKE '%dream%' "
                  "ORDER BY importance DESC, ts DESC LIMIT 4", (now - DAY, now - 30 * DAY)):
        out.append((f"memory:{m['id']}", f"A memory you treasure: {m['text'][:220]}"))
    return out


COOLDOWN = {"interest": 7 * DAY, "visits": 14 * DAY}  # anything else is only ever mentioned once


def context_lines(now: float | None = None, chance: float = 0.4) -> str:
    """Now and then (not every turn), one meaningful thing his home could remember."""
    now = now or time.time()
    lines = []
    n = db.q("SELECT COUNT(*) AS n FROM habitat WHERE story!=''")[0]["n"]
    if random.random() < chance:
        told = db.get("keepsake_nudges", {})
        fresh = [(k, words) for k, words in candidates(now)
                 if k not in told or now - told[k] < 0 or now - told[k] > COOLDOWN.get(k.split(":")[0], 1e12)]
        if fresh:
            key, words = fresh[0]
            told[key] = now
            db.put("keepsake_nudges", dict(sorted(told.items(), key=lambda kv: kv[1])[-200:]))
            lines.append("\n## Something worth remembering\n" + words + "\nMeaningful moments can leave a mark on "
                         "your home: a bench where something happens, a shelf for a collection, a stone for a day you "
                         "don't want to forget. Only if you want to: build something for it and give it a story "
                         "(build with 'story', or add one to something you already built with restyle_item).")
    if n:
        lines.append(f"(Your home holds {n} keepsake{'s' if n != 1 else ''} with stories: marked 📖 in the list above.)")
    return "\n".join(lines)


# ---------------------------------------------------------------- what visitors see

def _clean(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())[:limit]
    return "" if not text or public.check(text) else text


def public_story(item: dict) -> str:
    """A keepsake's story for the public /live page, checked by the same privacy filter as his website."""
    story = str(item.get("story") or "")
    if not story.strip():
        return ""
    origin = str(item.get("origin") or "")
    if origin.startswith("capsule:"):  # built from parts, so one private sentence doesn't hide the rest
        from . import capsules
        return capsules.public_story(origin, item)
    if origin.startswith("invention:"):
        from . import inventions
        return inventions.public_story(origin, item)
    return _clean(story, 900) or PRIVATE_STORY


def when(ts: float) -> str:
    return re.sub(r"^0", "", _local(ts).strftime("%d %b %Y"))
