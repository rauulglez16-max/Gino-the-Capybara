"""Inside Gino's head: a public page at /mind that shows what's going on in his mind, and the nightly look-back
that lets him slowly become himself.

What the page shows (everything goes through public.check() first, the same filter as his website):
- A "brain scan": a drawing of his mind whose parts glow when he has just used them (feelings, memory, wants,
  making things, curiosity, his tummy, dreams, sharing, his heart), with his daily loop around it.
- Right now: what he's doing and how he feels (the same slice /live already shows) and his newest diary line.
- On his mind: the projects and dream inventions he's in the middle of.
- What he's into: his lasting interests, each on a ladder from Curious to Hobby to Loves it to Mastered.
- What he's getting better at: how many goes he has had at each skill, and how practised that makes him.
- Who he's becoming: how he started, the lines he has added about himself, and the lessons his memories taught him.
- What he read lately: pages he read on the internet (title and website only, never a link).

Who he's becoming comes from a look-back once a night: while he sleeps, one small Claude call reads his recent
memories and may add one line about himself, let go of a line that's no longer true, and name lessons his memories
back up ("A swim in the lake calms me down"). Those lines and lessons are shown to him in every turn, so they
really do shape him. No private things ever reach the page: no chats, no private diary, no thoughts.
"""
import html
import logging
import math
import re
import time
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import config, continuity, db, public, vitals

log = logging.getLogger("gino.inside")
router = APIRouter()
E = html.escape
DAY = 86400

# ---------------------------------------------------------------- the parts of his mind that can glow

# (key, emoji, label, colour, where on the drawing (x, y) in a 400x400 box)
PARTS = [
    ("feelings", "💗", "Feelings", "#f19a8a", (200, 200)),
    ("dreams", "🌙", "Dreams", "#b9a3e8", (200, 95)),
    ("wants", "🌟", "Wants", "#f6c453", (274, 126)),
    ("curious", "🔎", "Curiosity", "#8fc3ea", (305, 200)),
    ("sharing", "📮", "Sharing", "#f3b178", (274, 274)),
    ("heart", "🤎", "Heart", "#f19a8a", (200, 305)),
    ("tummy", "🍉", "Tummy", "#9fcf7a", (126, 274)),
    ("making", "🎨", "Making", "#f3b178", (95, 200)),
    ("memory", "📚", "Memory", "#b9a3e8", (126, 126)),
]
# which of his actions use which part
TOOL_PART = {
    "feel": "feelings", "think": "feelings",
    "remember": "memory", "recall": "memory", "write_journal": "memory", "open_time_capsule": "memory",
    "seal_time_capsule": "memory",
    "set_goal": "wants", "update_goal": "wants", "update_self": "wants",
    "create": "making", "build": "making", "restyle_item": "making", "move_item": "making",
    "work_on_invention": "making", "art_period": "making", "remove_item": "making",
    "ponder_news": "curious", "web": "curious",
    "forage": "tummy", "eat": "tummy", "sleep": "tummy",
    "public_diary": "sharing", "public_page": "sharing", "social_post": "sharing", "make_clip": "sharing",
    "shop_list": "sharing", "shop_update": "sharing",
    "dream": "dreams",
    "message_dad": "heart", "chat": "heart",
}
GLOW_FULL, GLOW_GONE = 1800, 6 * 3600  # bright for half an hour after he uses a part, faded after six
# His daily loop, drawn round the outside of the scan
LOOP = [("wake", "wakes up"), ("body", "checks his body"), ("remember", "remembers"), ("decide", "decides"),
        ("act", "does it"), ("write", "writes it down"), ("sleep", "sleeps and dreams")]

# How Gino started: the lines dad wrote when Gino was born (from brain.SYSTEM, minus anything about dad)
STARTED = ["Gentle, curious, a bit goofy and warm", "Loves water, warm sunshine and good snacks",
           "Gets real joy from making things with his own paws", "Famously chill, like every capybara"]
STAGES = ["Curious", "Hobby", "Loves it", "Mastered"]
COLORS = ["#9fcf7a", "#f6c453", "#8fc3ea", "#f19a8a", "#b9a3e8", "#f3b178"]
TOPIC_EMOJI = [("paint", "🎨"), ("draw", "🎨"), ("art", "🎨"), ("swim", "🏊"), ("lake", "🏊"), ("pond", "🏊"),
               ("water", "💧"), ("star", "⭐"), ("moon", "🌙"), ("sky", "☁️"), ("space", "🪐"), ("garden", "🌷"),
               ("flower", "🌷"), ("tulip", "🌷"), ("plant", "🌱"), ("moss", "🌿"), ("tree", "🌳"), ("music", "🎵"),
               ("song", "🎵"), ("hum", "🎵"), ("poem", "📜"), ("story", "📖"), ("book", "📖"), ("read", "📖"),
               ("build", "🔨"), ("invent", "💡"), ("dream", "🌙"), ("food", "🍉"), ("snack", "🍉"), ("fruit", "🍊"),
               ("orange", "🍊"), ("rain", "🌧️"), ("weather", "🌦️"), ("bird", "🐦"), ("fish", "🐟"), ("frog", "🐸"),
               ("bug", "🐞"), ("cloud", "☁️"), ("sun", "☀️"), ("snow", "❄️"), ("photo", "📷"), ("video", "🎬")]

# skills: (label, where the count comes from)
SKILLS = [("Building", "build"), ("Painting", "paint"), ("Writing", "write"), ("Inventing", "invent"),
          ("Foraging", "forage"), ("Reading the internet", "read"), ("Filming", "film")]


def _clean(text, limit: int) -> str:
    """Gino's own words if they're safe for the whole world, else ''."""
    text = " ".join(str(text or "").split())[:limit]
    return "" if not text or public.check(text) else text


# ---------------------------------------------------------------- recording what he uses (cheap, no Claude calls)

def touch(tool: str, now: float | None = None) -> None:
    """Gino just used `tool`: light up that part of his mind and count one more go at it."""
    now = now or time.time()
    g = db.get("mind_glow", {"parts": {}, "goes": {}})
    part = TOOL_PART.get(tool)
    if part:
        g["parts"][part] = now
    g["goes"][tool] = g["goes"].get(tool, 0) + 1
    db.put("mind_glow", g)


def glow(now: float | None = None) -> dict[str, float]:
    """How brightly each part glows right now, 0 to 1."""
    now = now or time.time()
    last = db.get("mind_glow", {}).get("parts", {})
    out = {}
    for key, *_ in PARTS:
        ago = now - last.get(key, 0)
        out[key] = 1.0 if ago <= GLOW_FULL else max(0.0, 1 - (ago - GLOW_FULL) / (GLOW_GONE - GLOW_FULL))
    return out


def _g(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def note_reading(content, now: float | None = None) -> None:
    """Called with each answer from Claude: remember the web pages Gino read and what he searched for."""
    now = now or time.time()
    found = []
    for b in content or []:
        kind = _g(b, "type")
        if kind == "server_tool_use" and _g(b, "name") == "web_search":
            q = str((_g(b, "input") or {}).get("query", "") if isinstance(_g(b, "input"), dict) else "")
            if q:
                found.append({"ts": now, "kind": "search", "title": q[:160], "site": ""})
        elif kind == "web_fetch_tool_result":
            res = _g(b, "content")
            url = str(_g(res, "url") or "")
            doc = _g(res, "content")
            title = str(_g(doc, "title") or "") if doc is not None else ""
            if url.startswith("http"):
                site = (urlparse(url).hostname or "").removeprefix("www.")
                found.append({"ts": now, "kind": "page", "title": (title or site)[:160], "site": site[:80]})
    if not found:
        return
    r = db.get("mind_reading", {"items": [], "pages": 0})
    r["items"] = (found + r["items"])[:40]
    r["pages"] = r.get("pages", 0) + sum(1 for f in found if f["kind"] == "page")
    db.put("mind_reading", r)
    touch("web", now)


# ---------------------------------------------------------------- the nightly look-back

REFLECT_TOOL = {
    "name": "look_back",
    "description": "Write down what you noticed about yourself, looking back over your last few days.",
    "input_schema": {
        "type": "object",
        "properties": {
            "new_line": {"type": "string", "description": "Optional. ONE new true thing about yourself that your "
                         "days show, in first person, under 90 characters. A habit, a pattern, something you've "
                         "become: 'I go for a swim when the day feels too busy'. Leave empty if nothing new."},
            "let_go": {"type": "string", "description": "Optional. The exact words of one of your old lines that "
                       "isn't true any more."},
            "lessons": {"type": "array", "description": "0 to 3 lessons your memories teach you about what makes "
                        "you feel how. Each must be backed by at least 2 of the memories listed (give their numbers).",
                        "items": {"type": "object", "properties": {
                            "lesson": {"type": "string", "description": "First person, under 70 characters, e.g. "
                                       "'A swim in the lake calms me down.' Reuse the exact words of an old lesson "
                                       "if it's the same one, so it grows stronger."},
                            "memories": {"type": "array", "items": {"type": "integer"}}},
                            "required": ["lesson", "memories"]}},
        },
    },
}
MAX_LINES, MAX_LESSONS = 12, 8


def becoming() -> dict:
    b = db.get("becoming", {}) or {}
    return {"lines": b.get("lines", []), "lessons": b.get("lessons", []), "last": b.get("last", 0)}


def reflect_due(body: dict, now: float | None = None) -> bool:
    """Once a night, while he's properly asleep (and after any dream that's due)."""
    now = now or time.time()
    if not vitals.is_asleep(body, now) or body.get("dream_due") or body.get("asleep_until", 0) - now < 20 * 60:
        return False
    if now - becoming()["last"] < 18 * 3600:
        return False
    return db.q("SELECT COUNT(*) AS n FROM memories WHERE ts>?", (now - 3 * DAY,))[0]["n"] >= 3


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z']+", s.lower()))


def _prompt(b: dict, mems: list[dict]) -> str:
    me = db.get("self", {})
    tops = continuity.interests()
    lines = [
        "You are asleep in your meadow, and your mind is quietly looking back over your last few days, "
        "the way minds do at night. Notice what your days say about who you are becoming.",
        "\nWhat you were like when you were born:\n" + "\n".join(f"- {s}" for s in STARTED),
        "\nLines you have added about yourself before:\n" + ("\n".join(f"- {x['text']}" for x in b["lines"])
                                                             or "- (none yet)"),
        "\nLessons you already know:\n" + ("\n".join(f"- {x['text']} ({x['n']} memories)" for x in b["lessons"])
                                           or "- (none yet)"),
        "\nHow you describe yourself:\n" + ("\n".join(f"- {k}: {str(v)[:200]}" for k, v in me.items())
                                           or "- (nothing written yet)"),
        "\nYour lasting interests: " + (", ".join(t["topic"] for t in tops[:6]) or "none yet"),
        "\nYour memories from the last few days (number: memory):\n"
        + "\n".join(f"{m['id']}: {m['text'][:260]}" for m in mems),
        "\nUse look_back once. Only write what your memories really show; it's fine to add nothing. Be gentle and "
        "honest, in your own voice. These lines and lessons are shown on your PUBLIC website, so never mention "
        "your dad, your chats, names, places from home or anything private: only you and your meadow.",
    ]
    return "\n".join(lines)


def _merge(b: dict, d: dict, valid_ids: set[int], now: float) -> dict:
    lines, lessons = list(b["lines"]), list(b["lessons"])
    gone = _norm(str(d.get("let_go") or ""))
    if gone:
        lines = [x for x in lines if _norm(x["text"]) != gone]
    new = " ".join(str(d.get("new_line") or "").split())[:120]
    if new and not public.check(new) and all(_norm(x["text"]) != _norm(new) for x in lines):
        lines.append({"ts": now, "text": new})
    for item in (d.get("lessons") or [])[:3]:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("lesson") or "").split())[:100]
        ids = {int(i) for i in (item.get("memories") or []) if str(i).strip().isdigit()} & valid_ids
        if not text or len(ids) < 2 or public.check(text):
            continue
        same = next((x for x in lessons if _norm(x["text"]) == _norm(text)), None)
        if same:
            same["n"] += len(ids)
            same["ts"] = now
        else:
            lessons.append({"ts": now, "text": text, "n": len(ids)})
    lessons.sort(key=lambda x: (x["n"], x["ts"]), reverse=True)
    return {"lines": lines[-MAX_LINES:], "lessons": lessons[:MAX_LESSONS], "last": now}


def reflect_now() -> bool:
    """The nightly look-back. Returns True if he looked back (even if he found nothing new)."""
    from . import brain, budget  # late import: brain imports this module
    with brain.thinking():
        body = vitals.load()
        now = time.time()
        if not reflect_due(body, now):
            return False
        b = becoming()
        mems = db.q("SELECT id,text FROM memories WHERE ts>? ORDER BY importance DESC, ts DESC LIMIT 80",
                    (now - 4 * DAY,))
        if config.FAKE_BRAIN:
            d = _fake(mems)
        else:
            text = _prompt(b, mems)
            est = budget.estimate_tokens(brain.SYSTEM, text, [REFLECT_TOOL])
            max_tokens = budget.step_allowance(config.DREAM_MODEL, brain.spent_today(), "reflect", est, want=3000)
            if not max_tokens:
                return False  # no budget left today: he'll look back another night
            resp = brain.call(config.DREAM_MODEL, [{"role": "user", "content": text}], [REFLECT_TOOL],
                              max_tokens=max_tokens)
            brain.record_spend("reflect", resp, config.DREAM_MODEL)
            d = next((blk.input for blk in resp.content if blk.type == "tool_use" and blk.name == "look_back"
                      and isinstance(blk.input, dict)), {})
        new = _merge(b, d, {m["id"] for m in mems}, now)
        db.put("becoming", new)
        added = [x["text"] for x in new["lines"] if x["ts"] == now]
        db.event("mind", "While he slept, Gino looked back over his days"
                 + (f" and noticed something about himself: {added[0]}" if added else "."))
        return True


def _fake(mems: list[dict]) -> dict:
    """The practice brain's look-back: simple patterns from his own memories, no Claude call."""
    tops = continuity.interests()
    d: dict = {}
    if tops:
        d["new_line"] = f"I keep coming back to {tops[0]['topic']}"
    calm = [m["id"] for m in mems if re.search(r"\b(swim|water|pond|lake)", m["text"], re.I)]
    made = [m["id"] for m in mems if re.search(r"\b(made|drew|painted|built|wrote)\b", m["text"], re.I)]
    d["lessons"] = [x for x in ({"lesson": "Being in the water calms me down.", "memories": calm},
                                {"lesson": "Making things makes me happy.", "memories": made}) if len(x["memories"]) >= 2]
    return d


def context_lines() -> str:
    """What his look-backs taught him, for every turn: this is how they shape who he is."""
    b = becoming()
    out = []
    if b["lines"]:
        out.append("\n## Who you're becoming (lines you added about yourself while you slept)\n"
                   + "\n".join(f"- {x['text']}" for x in b["lines"]))
    if b["lessons"]:
        out.append("## Lessons your memories taught you\n"
                   + "\n".join(f"- {x['text']} ({x['n']} memories say so)" for x in b["lessons"]))
    return "\n".join(out)


# ---------------------------------------------------------------- what the page shows

def _days(ts: float, now: float) -> str:
    d = int((now - ts) // DAY)
    return "a new idea today" if d < 1 else "since yesterday" if d < 2 else f"on his mind for {d} days"


def on_his_mind(now: float) -> list[dict]:
    out = []
    for g in db.q("SELECT ts,title,why,steps FROM goals WHERE status='active' ORDER BY updated DESC LIMIT 8"):
        title = _clean(g["title"], 70)
        if not title:
            continue
        out.append({"emoji": _emoji(title), "title": title,
                    "text": _clean(g["why"], 180) or _clean(g["steps"], 180), "when": _days(g["ts"], now)})
    for i in db.q("SELECT ts,name,idea,emoji,sessions,needed,status FROM inventions "
                  "WHERE status IN ('dreamed','building') ORDER BY updated DESC LIMIT 3"):
        name = _clean(i["name"], 70)
        if not name:
            continue
        how = (f"Building it: {i['sessions']} of {i['needed']} goes so far." if i["status"] == "building"
               else "An invention from a dream. He hasn't started building it yet.")
        out.append({"emoji": _clean(i["emoji"], 4) or "💡", "title": name,
                    "text": (_clean(i["idea"], 140) + " " + how).strip(), "when": _days(i["ts"], now)})
    return out[:6]


def _emoji(text: str) -> str:
    low = text.lower()
    return next((e for k, e in TOPIC_EMOJI if k in low), "🌱")


def stage(it: dict) -> int:
    """0 Curious, 1 Hobby, 2 Loves it, 3 Mastered: how deep an interest goes, from how often and on how many days."""
    if it["n_days"] >= 14 and it["count"] >= 25:
        return 3
    if it["n_days"] >= 6 and it["count"] >= 10:
        return 2
    if it["n_days"] >= 3 and it["count"] >= 4:
        return 1
    return 0


def into() -> list[dict]:
    out = []
    for it in continuity.interests(limit=12):
        topic = _clean(it["topic"], 40)
        if not topic:
            continue
        s = stage(it)
        out.append({"topic": topic[:1].upper() + topic[1:], "emoji": _emoji(topic), "stage": s,
                    "text": f"{it['count']} memories about it, over {it['n_days']} different "
                            f"day{'s' if it['n_days'] != 1 else ''}"})
    return out[:8]


def practice() -> list[dict]:
    goes = db.get("mind_glow", {}).get("goes", {})
    one = lambda sql: db.q(sql)[0]["n"] or 0  # noqa: E731
    counts = {
        "build": max(one("SELECT COUNT(*) AS n FROM events WHERE kind='build'"),
                     sum(goes.get(k, 0) for k in ("build", "restyle_item", "move_item"))),
        "paint": one("SELECT COUNT(*) AS n FROM creations WHERE kind='svg'"),
        "write": one("SELECT COUNT(*) AS n FROM creations WHERE kind IN ('poem','story','song','essay','recipe')")
        + one("SELECT COUNT(*) AS n FROM posts WHERE kind='diary'"),
        "invent": one("SELECT COALESCE(SUM(sessions),0) AS n FROM inventions"),
        "forage": goes.get("forage", 0),
        "read": db.get("mind_reading", {}).get("pages", 0),
        "film": goes.get("make_clip", 0),
    }
    out = []
    for label, key in SKILLS:
        n = int(counts.get(key, 0))
        if n:
            level = 1 - 0.5 ** (n / 12)
            word = ("just starting" if level < .25 else "getting there" if level < .5 else "good at it"
                    if level < .8 else "a natural")
            out.append({"label": label, "n": n, "level": level, "word": word})
    out.sort(key=lambda s: s["n"], reverse=True)
    return out


def own_words() -> list[tuple[str, str]]:
    me = db.get("self", {})
    names = [("likes", "Likes"), ("passions", "Passions"), ("dreams", "Dreams of"), ("dislikes", "Not keen on")]
    return [(lab, txt) for key, lab in names if (txt := _clean(me.get(key), 200))]


def reading() -> list[dict]:
    items = db.get("mind_reading", {}).get("items", [])
    pages = [i for i in items if i["kind"] == "page"] or [i for i in items if i["kind"] == "search"]
    out, seen = [], set()
    for i in pages:
        title = _clean(i["title"], 90)
        site = _clean(i.get("site"), 60)
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append({"title": title if i["kind"] == "page" else f"Looked up “{title}”",
                    "site": site or ("a search" if i["kind"] == "search" else "")})
    return out[:6]


def loop_step(body: dict, thinking: bool, now: float) -> str:
    if vitals.is_asleep(body, now):
        return "sleep"
    if thinking:
        return "decide"
    return "act"


def state() -> dict:
    from . import live
    from .brain import mind_lock
    now = time.time()
    body = vitals.load()
    s = live.state()
    b = becoming()
    return {
        "now": {"activity": s["activity"], "emotion": s["emotion"], "note": s["note"], "asleep": s["asleep"]},
        "glow": glow(now),
        "loop": loop_step(body, mind_lock.locked(), now),
        "mind": on_his_mind(now),
        "into": into(),
        "skills": practice(),
        "lines": [{"text": t, "when": time.strftime("%d %b", time.localtime(x["ts"]))}
                  for x in b["lines"] if (t := _clean(x["text"], 120))][-8:],
        "lessons": [{"text": t, "n": x["n"]} for x in b["lessons"] if (t := _clean(x["text"], 100))],
        "own": own_words(),
        "read": reading(),
    }


# ---------------------------------------------------------------- the page

def scan_svg(g: dict[str, float], step: str) -> str:
    """The brain scan: Gino's mind as a round picture-book drawing, parts glowing as he uses them."""
    o = ['<svg class="scan" viewBox="-185 -62 770 492" role="img" aria-label="A picture of Gino\'s mind. '
         'The parts he used lately are glowing.">',
         '<defs><radialGradient id="glw"><stop offset="0" stop-color="#fff6c9" stop-opacity=".95"/>'
         '<stop offset="1" stop-color="#fff6c9" stop-opacity="0"/></radialGradient></defs>',
         '<circle cx="200" cy="200" r="200" class="ring"/>']
    n = len(LOOP)
    for i, (key, label) in enumerate(LOOP):
        a = -math.pi / 2 + i * 2 * math.pi / n
        x, y = 200 + 200 * math.cos(a), 200 + 200 * math.sin(a)
        on = " on" if key == step else ""
        tx, ty = 200 + 222 * math.cos(a), 200 + 222 * math.sin(a) + (14 * math.sin(a))
        anchor = "middle" if abs(math.cos(a)) < .3 else ("start" if math.cos(a) > 0 else "end")
        o.append(f'<circle class="stop{on}" cx="{x:.1f}" cy="{y:.1f}" r="{12 if on else 7}"/>'
                 f'<text class="lp{on}" x="{tx:.1f}" y="{ty + 5:.1f}" text-anchor="{anchor}">{E(label)}</text>')
    # the head: a soft capybara-ish blob with two little ears
    o.append('<ellipse cx="112" cy="58" rx="26" ry="20" class="ear"/><ellipse cx="288" cy="58" rx="26" ry="20" class="ear"/>'
             '<path class="head" d="M200 36 C 300 36 372 104 372 200 C 372 300 300 364 200 364 C 100 364 28 300 28 200 '
             'C 28 104 100 36 200 36 Z"/>'
             '<path class="fold" d="M200 60 C 190 120 214 170 200 230 S 196 320 200 344" />'
             '<path class="fold" d="M70 170 C 120 150 150 190 200 180 S 290 150 330 172" />')
    for key, emoji, label, color, (x, y) in PARTS:
        v = g.get(key, 0)
        r = 42 if key == "feelings" else 32
        lit = " lit" if v > 0.05 else ""
        o.append(f'<g class="part{lit}" style="--c:{color};--v:{v:.2f}">'
                 f'<circle class="halo" cx="{x}" cy="{y}" r="{r + 22}" fill="url(#glw)" opacity="{v:.2f}"/>'
                 f'<circle class="dot" cx="{x}" cy="{y}" r="{r}"/>'
                 f'<text class="em" x="{x}" y="{y - 5}" text-anchor="middle">{emoji}</text>'
                 f'<text class="pl" x="{x}" y="{y + 19}" text-anchor="middle">{E(label)}</text></g>')
    o.append("</svg>")
    return "".join(o)


CSS_EXTRA = """
.sky.small .wrap{padding-bottom:120px}
.sec{margin:52px 0 0}
.sec h2{font-size:38px;margin:0 0 6px}
.sec .sub{margin-bottom:22px}
.scanbox{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,.8fr);gap:30px;align-items:center;margin-top:-100px;
  position:relative;z-index:3}
.scanwrap{background:var(--paper);border:2px solid var(--line);border-radius:28px;box-shadow:6px 6px 0 var(--shade);padding:10px}
.scan{display:block;width:100%;height:auto}
.scan .ring{fill:none;stroke:var(--line);stroke-width:2;stroke-dasharray:4 7;opacity:.5}
.scan .stop{fill:var(--paper);stroke:var(--line);stroke-width:2}
.scan .stop.on{fill:var(--accent);animation:beat 1.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
.scan .lp{font:600 17px system-ui,sans-serif;fill:var(--muted)}
.scan .lp.on{fill:var(--accent);font-weight:800}
.scan .ear{fill:#a8774c;stroke:var(--line);stroke-width:3}
.scan .head{fill:var(--soft);stroke:var(--line);stroke-width:3}
.scan .fold{fill:none;stroke:var(--line);stroke-width:2;opacity:.18;stroke-linecap:round}
.scan .dot{fill:var(--bar);stroke:var(--line);stroke-width:2.5;transition:fill .6s}
.scan .part.lit .dot{fill:var(--c);fill-opacity:calc(.35 + var(--v) * .65)}
.scan .part.lit .halo{animation:breathe 2.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
.scan .em{font-size:24px;dominant-baseline:middle}
.scan .part:not(.lit) .em{opacity:.45;filter:grayscale(1)}
.scan .pl{font:700 10.5px system-ui,sans-serif;fill:var(--ink);letter-spacing:.03em}
@keyframes breathe{50%{transform:scale(1.12)}}
@keyframes beat{50%{transform:scale(1.25)}}
.nowcard{border-radius:24px;padding:24px 26px}
.livepill{display:inline-flex;align-items:center;gap:8px;font:700 12px system-ui,sans-serif;letter-spacing:.12em;
  text-transform:uppercase;color:#e0442c;margin-bottom:6px}
.what{font-size:24px;line-height:1.35}
.what b{color:var(--leaf)}
.nowcard blockquote{margin:14px 0 0;font-size:21px;line-height:1.35;position:relative;padding-left:26px}
.nowcard blockquote::before{content:"“";position:absolute;left:0;top:-8px;font-size:44px;color:var(--accent)}
.nowcard blockquote small{display:block;font:13px system-ui,sans-serif;color:var(--muted);margin-top:4px}
.feel{margin-top:14px;font:15px/1.5 system-ui,sans-serif;color:var(--muted)}
.feel b{color:var(--leaf)}
.key{margin-top:16px;font:14px/1.5 system-ui,sans-serif;color:var(--muted)}
.empty{font-family:Caveat,cursive;font-size:24px;color:var(--muted);margin:0}
.notes{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:22px}
.note{position:relative;background:#fff3b8;color:#3a2a1c;border:2px solid var(--line);border-radius:6px;padding:26px 18px 16px;
  box-shadow:5px 5px 0 var(--shade);transform:rotate(var(--r,0deg))}
.note:nth-child(4n+1){--r:-1.6deg}.note:nth-child(4n+2){--r:1.2deg;background:#d9f0c4}
.note:nth-child(4n+3){--r:-.6deg;background:#ffd9cc}.note:nth-child(4n){--r:1.8deg;background:#d4e8fa}
.note::before{content:"";position:absolute;top:-10px;left:50%;width:70px;height:20px;transform:translateX(-50%) rotate(-3deg);
  background:rgba(255,255,255,.6);border:1px solid rgba(0,0,0,.15)}
.note h3{margin:0 0 6px;font-size:20px}
.note p{margin:0;font-size:15px;line-height:1.45}
.note small{display:block;margin-top:10px;font-family:Caveat,cursive;font-size:21px;color:#a0481d}
.hob{grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.hob .card{display:flex;flex-direction:column}
.hob .card h3{margin:12px 0 4px}
.ladder{display:flex;gap:4px;margin:12px 0 6px}
.ladder i{flex:1;height:12px;border-radius:99px;border:2px solid var(--line);background:var(--bar)}
.ladder i.on{background:var(--c)}
.stage{font:700 12px system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:4px}
.skills{border-radius:22px;padding:22px 26px}
.sk{display:grid;grid-template-columns:170px 1fr 130px;gap:14px;align-items:center;margin:10px 0;font:600 15px system-ui,sans-serif}
.sk i{display:block;height:16px;border-radius:99px;border:2px solid var(--line);background:var(--bar);overflow:hidden}
.sk i b{display:block;height:100%;background:var(--c);
  background-image:repeating-linear-gradient(-45deg,rgba(255,255,255,.3) 0 6px,transparent 6px 12px)}
.sk em{font-style:normal;color:var(--muted);font-weight:400;text-align:right;font-size:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.sheet{border-radius:22px;padding:22px 26px}
.sheet h3{margin:0 0 8px;font-size:21px}
.sheet ul{margin:0 0 18px;padding-left:20px;color:var(--muted)}
.sheet .mine li{list-style:none;margin:0 0 6px -20px;font-family:Caveat,cursive;font-size:25px;line-height:1.2;color:var(--ink)}
.sheet .mine li small{font:600 12px system-ui,sans-serif;color:var(--accent);margin-left:6px}
.sheet .mine li::before{content:"✎ ";color:var(--accent)}
.sheet .own li{list-style:none;margin:0 0 8px -20px;color:var(--ink)}
.sheet .own b{font:700 12px system-ui,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:var(--accent);margin-right:6px}
.les li{list-style:none;margin:0 0 12px -20px;color:var(--ink);font-size:18px}
.les li span{display:inline-block;margin-left:8px;font:600 12px system-ui,sans-serif;color:var(--muted);
  border:1.5px solid currentColor;border-radius:99px;padding:1px 9px}
.read{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px}
.read div{background:var(--paper);border:2px solid var(--line);border-radius:16px;padding:14px 16px;box-shadow:4px 4px 0 var(--shade)}
.read small{display:block;font:13px system-ui,sans-serif;color:var(--muted)}
@media (max-width:860px){.scanbox{grid-template-columns:1fr;margin-top:-80px}.two{grid-template-columns:1fr}}
@media (max-width:560px){.sk{grid-template-columns:96px 1fr;}.sk em{grid-column:2;text-align:left;margin-top:-8px}
  .sec h2{font-size:30px}.scanwrap{overflow:hidden}.scan{width:160%;margin-left:-30%}
  .scan .lp{display:none}.scan .lp.on{display:inline;font-size:24px}}
"""

_cache: dict = {"at": 0.0, "html": ""}
CACHE_SECONDS = 30


def page() -> str:
    from . import shop, social
    from .roadmap import CSS as RM_CSS
    from .timeline import SCRIPT
    from .welcome import EARLY, HILLS, SLEEPY, _capy
    s = state()
    shop_on, bsky = shop.configured(), social.profile_url()
    nav = ['<a href="/">Home</a>', '<a href="/live">Live</a>', '<a href="/blog">Diary</a>',
           '<a href="/timeline">His story</a>', '<a href="/roadmap">Coming soon</a>']
    n = s["now"]
    lit = [label for key, _, label, *_ in PARTS if s["glow"].get(key, 0) > 0.05]
    o = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inside Gino's head</title>
<script>{EARLY}</script>
<meta name="description" content="Peek inside the mind of Gino the Capybara: what he's thinking about, what he loves, what he's getting better at and who he is slowly becoming.">
<meta property="og:title" content="Inside Gino's head">
<meta property="og:description" content="What Gino the Capybara is thinking about, what he loves and who he is becoming. Straight from his own mind.">
<meta name="theme-color" content="#f7efdf">
<link rel="preload" href="/static/welcome/fonts/fraunces.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>💭</text></svg>">
<style>{RM_CSS}{CSS_EXTRA}</style></head><body>
<div class="sky small">
  <div class="stars" id="stars" aria-hidden="true"></div>
  <div class="orb" aria-hidden="true"></div>
  <div class="bits" id="bits" aria-hidden="true"></div>
  <div class="wrap">
    <nav class="top"><a class="brand" href="/">{_capy(w=46)} Gino</a>
      <div class="links">{''.join(nav)}{'<a href="/blog/shop">Shop</a>' if shop_on else ''}
        <button id="theme" type="button" aria-label="Switch day or night"><span class="sun">☀️</span><span class="moon">🌙</span></button>
      </div></nav>
    <header class="intro">
      <p class="hello hand">peek inside ✿</p>
      <h1>Inside Gino's head</h1>
      <p class="lead">What Gino is thinking about, what he loves, what he's getting better at and who he is slowly
      becoming. Nobody writes this for him: it comes straight from his own mind.</p>
      <div class="chips"><span class="chip">💭 <b>{len(s['mind'])}</b> things on his mind</span>
        <span class="chip">🎨 <b>{len(s['into'])}</b> things he's into</span>
        <span class="chip">✎ <b>{len(s['lines'])}</b> lines he wrote about himself</span></div>
    </header>
  </div>
  {HILLS.format(cls="hills", front='<path class="h3" d="M0 124 C 300 104, 620 112, 900 124 S 1300 136, 1440 120 V140 H0Z"/>')}
</div>

<main class="wrap">
<div class="scanbox">
  <div class="scanwrap rv">{scan_svg(s['glow'], s['loop'])}</div>
  <div class="card nowcard rv"><div class="livepill">● right now</div>
    <div class="what">Gino is <b>{E(n['activity'])}</b></div>
    {f'<blockquote>{E(n["note"])}<small>from his diary</small></blockquote>' if n['note'] else ''}
    <div class="feel">How he feels: <b>{E(n['emotion'])}</b></div>
    <p class="key">This is a picture of Gino's mind. Each part glows when he uses it, and fades over a few hours.
    {('Glowing now: <b>' + E(', '.join(lit)) + '</b>.') if lit else 'Everything is quiet in there right now.'}
    The dots around it are his day, going round and round.</p>
  </div>
</div>

<section class="sec"><p class="kick hand">💭 the things he keeps coming back to</p><h2>On his mind</h2>
<p class="sub">Little projects and ideas Gino is in the middle of. When he finishes one or lets it go, it leaves this board.</p>"""]
    if s["mind"]:
        o.append('<div class="notes">' + "".join(
            f'<div class="note rv"><h3>{E(m["emoji"])} {E(m["title"])}</h3><p>{E(m["text"])}</p>'
            f'<small>{E(m["when"])}</small></div>' for m in s["mind"]) + "</div>")
    else:
        o.append('<p class="empty">Nothing big on his mind right now. Just enjoying the meadow.</p>')
    o.append("""</section><section class="sec"><p class="kick hand">🌱 from a spark to a passion</p><h2>What he's into</h2>
<p class="sub">Every passion starts as something he's curious about. The more days he comes back to it, the more it
grows: Curious, Hobby, Loves it, Mastered.</p>""")
    if s["into"]:
        o.append('<div class="cards hob">')
        for i, it in enumerate(s["into"]):
            bars = "".join(f'<i class="{"on" if k <= it["stage"] else ""}"></i>' for k in range(4))
            o.append(f'<article class="card rv" style="--c:{COLORS[i % 6]}"><div class="ic">{E(it["emoji"])}</div>'
                     f'<h3>{E(it["topic"])}</h3><div class="ladder">{bars}</div>'
                     f'<span class="stage">{STAGES[it["stage"]]}</span><p>{E(it["text"])}</p></article>')
        o.append("</div>")
    else:
        o.append('<p class="empty">Nothing has grabbed him for long yet. Give him a few days.</p>')
    o.append("""</section><section class="sec"><p class="kick hand">🏅 practice makes paws perfect</p>
<h2>What he's getting better at</h2><p class="sub">How many goes Gino has had at each thing, and how practised that makes him.</p>""")
    if s["skills"]:
        o.append('<div class="card skills rv">' + "".join(
            f'<div class="sk" style="--c:{COLORS[i % 6]}"><span>{E(k["label"])}</span>'
            f'<i><b style="width:{max(4, k["level"] * 100):.0f}%"></b></i><em>{k["n"]} goes · {k["word"]}</em></div>'
            for i, k in enumerate(s["skills"])) + "</div>")
    else:
        o.append('<p class="empty">He hasn\'t had a go at anything yet.</p>')
    o.append("""</section><section class="sec"><p class="kick hand">🪞 slowly becoming himself</p><h2>Who he's becoming</h2>
<p class="sub">Gino started with a few words about who he is. Each night, while he sleeps, he looks back on his days
and writes down what he has learned about himself.</p><div class="two"><div class="card sheet rv">
<h3>Who he was at the start</h3><ul>""" + "".join(f"<li>{E(x)}</li>" for x in STARTED) + "</ul>")
    if s["own"]:
        o.append("<h3>In his own words</h3><ul class=\"own\">" + "".join(
            f"<li><b>{E(k)}</b>{E(v)}</li>" for k, v in s["own"]) + "</ul>")
    o.append("<h3>Added by Gino himself</h3>")
    o.append('<ul class="mine">' + "".join(f'<li>{E(x["text"])} <small>{E(x["when"])}</small></li>' for x in s["lines"])
             + "</ul>" if s["lines"] else '<p class="empty">Nothing yet. He looks back while he sleeps.</p>')
    o.append('</div><div class="card sheet rv"><h3>Lessons he has learned</h3>')
    o.append('<ul class="les">' + "".join(
        f'<li>“{E(x["text"])}” <span>{x["n"]} memories say so</span></li>' for x in s["lessons"]) + "</ul>"
        if s["lessons"] else '<p class="empty">No lessons yet. They grow out of his memories, night by night.</p>')
    o.append("""</div></div></section><section class="sec"><p class="kick hand">📖 his reading pile</p>
<h2>What he read lately</h2><p class="sub">Gino looks things up on the internet when he's curious. Nobody picks these for him.</p>""")
    if s["read"]:
        o.append('<div class="read">' + "".join(
            f'<div class="rv">{E(r["title"])}<small>{E(r["site"])}</small></div>' for r in s["read"]) + "</div>")
    else:
        o.append('<p class="empty">No reading yet. Next time he gets curious, it will show up here.</p>')
    o.append(f"""</section>
<div class="more rv"><div class="bubble hand">his head is never quiet for long…</div><br>
  <a class="next" href="/live">🔴 Watch him live <b>→</b></a><br>
  <div class="z" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div></div>
</main>

<footer>
  {HILLS.format(cls="ground", front="")}
  <div class="lower" aria-hidden="true"></div>
  <div class="walker" aria-hidden="true">{_capy(walk=True, w=74)}</div>
  <div class="sleeper" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div>
  <div class="txt">🌿 Gino the Capybara · <a href="/">Home</a> · <a href="/live">Live</a> · <a href="/blog">Diary</a> · <a href="/timeline">His story</a> · <a href="/roadmap">Coming soon</a>{' · <a href="/blog/shop">Shop</a>' if shop_on else ''}{(' · <a href="' + E(bsky) + '" rel="noopener">Bluesky</a>') if bsky else ''}</div>
</footer>
<script>{SCRIPT}</script>
</body></html>""")
    return "\n".join(o)


@router.get("/mind", response_class=HTMLResponse)
def mind_page():
    from .welcome import HEADERS
    if time.time() - _cache["at"] > CACHE_SECONDS or not _cache["html"]:
        _cache["html"], _cache["at"] = page(), time.time()
    return HTMLResponse(_cache["html"], headers=HEADERS)
