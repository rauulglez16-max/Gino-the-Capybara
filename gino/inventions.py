"""Dream inventions: some nights a dream fuses familiar things into something that doesn't exist yet.

A mushroom lantern, a floating vegetable garden, a telescope that looks underwater. When Gino wakes up he can
sketch it (a drawing linked to the invention) and try to build it with work_on_invention. Building takes a few
work sessions spread over several days, because his paws need rest between sessions. When it's finished it
appears in his 3D world with its story. Sometimes it doesn't come out the way he dreamed it, and he gets to say
what he thinks about that.

No extra cost: the invention comes with the dream he was already having, and building happens in his ordinary turns.
"""
import json
import random
import re
import time

from . import config, db, keepsakes, public

DAY = 86400
SESSION_GAP_HOURS = 4  # rest between work sessions, so building takes days, not minutes
MAX_OPEN = 3  # at most three unbuilt inventions on his mind; older ones quietly fade

# What can go differently from the dream: (words, change to the item). Words work for Gino and for visitors.
TWISTS = [
    ("it came out much smaller than in the dream", {"size": 0.6}),
    ("it came out far bigger than planned", {"size": 1.8}),
    ("it's a completely different colour from the dream", {"recolour": True}),
    ("it leans a little to one side, however it gets propped up", {}),
    ("it works, but only sort of, and only when nobody is looking", {}),
    ("it hums quietly to itself, which it never did in the dream", {}),
    ("it turned out more like a lamp than what was dreamed", {"kind": "lamp"}),
    ("one part just wouldn't stay on, so it's simpler than the dream", {"size": 0.85}),
]
TWIST_CHANCE = 0.4
COLOURS = ["#e07a3a", "#7a5cc9", "#3f9acb", "#d94f7a", "#5aa86b", "#e8c13a"]


def _txt(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


# ---------------------------------------------------------------- in the dream

DREAM_FIELD = {
    "type": "object",
    "description": "ONLY if tonight's dream invents something: an object that doesn't exist yet, fused from familiar "
                   "things. Leave it out otherwise.",
    "properties": {
        "name": {"type": "string", "description": "What you'd call it, e.g. 'mushroom lantern'"},
        "idea": {"type": "string", "description": "What it is and does in the dream, one or two sentences"},
        "made_from": {"type": "array", "items": {"type": "string"},
                      "description": "The familiar things it fuses together"},
        "emoji": {"type": "string", "description": "One emoji for it"},
        "looks_like": {"type": "string", "description": "The closest everyday shape, one of: " + ", ".join(
            ["lamp", "tree", "mushroom", "flowers", "garden", "telescope", "statue", "fountain", "boat", "bench",
             "windmill", "tent", "arch", "bridge", "beehive", "piano", "swing", "sign", "other"])},
    },
}

INVENT_PROMPT = ("\nTonight the dream INVENTS something: it fuses two or more familiar things (from your home, "
                 "things you've made, things you love) into an object that doesn't exist yet, like a mushroom "
                 "lantern, a floating vegetable garden or a telescope that looks underwater. It should be something a "
                 "capybara could try to build. Describe it in the 'invention' field as well as in the story.")


def should_invent(level: int) -> bool:
    """Not every dream invents something; stranger dreams more often do. Never with too many unbuilt ideas."""
    if len(db.q("SELECT id FROM inventions WHERE status IN ('dreamed','building')")) >= MAX_OPEN:
        return False
    return random.random() < (0.2 if level <= 2 else 0.4)


def from_dream(dream_id: int, inv) -> int | None:
    """Save an invention that came with a dream. Returns its id."""
    if not isinstance(inv, dict) or len(db.q("SELECT id FROM inventions WHERE status IN ('dreamed','building')")) \
            >= MAX_OPEN:
        return None
    name, idea = _txt(inv.get("name"), 50), _txt(inv.get("idea"), 500)
    if not name or not idea:
        return None
    from .tools import KINDS  # late import: tools imports this module
    kind = str(inv.get("looks_like") or "").lower().strip()
    kind = kind if kind in KINDS and kind not in ("auto", "capsule") else ""
    made = inv.get("made_from") or []
    if isinstance(made, str):
        made = [m.strip() for m in made.split(",")]
    made = [_txt(m, 60) for m in made if _txt(m, 60)][:5]
    now = time.time()
    iid = db.x("INSERT INTO inventions(ts,updated,dream_id,name,idea,made_from,kind,emoji,needed) "
               "VALUES(?,?,?,?,?,?,?,?,?)",
               (now, now, dream_id, name, idea, json.dumps(made), kind, _txt(inv.get("emoji"), 4) or "✨",
                random.randint(3, 4)))
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (now, f"My dream invented something: a {name}. {idea}", 3, "invention, dream"))
    db.event("dream", f"dreamed up an invention: {name}")
    return iid


def waking_lines(dream_id: int) -> str:
    rows = db.q("SELECT * FROM inventions WHERE dream_id=?", (dream_id,))
    if not rows:
        return ""
    i = rows[0]
    made = json.loads(i["made_from"] or "[]")
    return (f"\n**Your dream invented something: the {i['name']}** (invention #{i['id']}). {i['idea']}"
            + (f" It was made of {', '.join(made)}." if made else "")
            + f"\nYou could sketch it before it fades (create, kind 'svg', with invention_id {i['id']}) and try to "
              "build it for real with work_on_invention: it takes a few sessions over several days. Or let it go.")


# ---------------------------------------------------------------- building it

def link_sketch(invention_id, creation_id: int) -> str:
    try:
        iid = int(invention_id)
    except (TypeError, ValueError):
        return ""
    rows = db.q("SELECT name FROM inventions WHERE id=?", (iid,))
    if not rows:
        return ""
    db.x("UPDATE inventions SET sketch_id=?, updated=? WHERE id=?", (creation_id, time.time(), iid))
    db.x("UPDATE creations SET invention_id=? WHERE id=?", (iid, creation_id))
    return f" It's your sketch of the {rows[0]['name']}."


def _story(i: dict, opinion: str = "") -> str:
    dreamt = keepsakes.when(i["ts"])
    s = f"Gino dreamed this up on {dreamt}: {i['idea']}"
    if i.get("sessions"):
        s += f" He built it over {i['sessions']} work sessions."
    if i.get("twist"):
        s += f" It didn't come out quite as dreamed: {i['twist']}."
    if opinion:
        s += f" What Gino thinks of it: “{opinion}”"
    return s


def work(body: dict, a: dict) -> str:
    now = time.time()
    try:
        iid = int(a.get("invention_id") or 0)
    except (TypeError, ValueError):
        iid = 0
    rows = db.q("SELECT * FROM inventions WHERE id=?", (iid,))
    if not rows:
        return f"There's no invention #{iid}."
    i = rows[0]
    opinion, note = _txt(a.get("opinion"), 600), _txt(a.get("note"), 400)
    if a.get("give_up"):
        if i["status"] == "built":
            return "It's already built. You could take it out of your home with remove_item if you don't want it."
        db.x("UPDATE inventions SET status='abandoned', opinion=?, updated=? WHERE id=?", (opinion or note, now, iid))
        db.event("build", f"gave up on building the {i['name']}")
        return f"You let the {i['name']} go. Not every dream has to be built."
    if i["status"] in ("built", "abandoned"):
        if not opinion:
            return f"The {i['name']} is already {i['status']}. You can still say what you think of it (opinion)."
        db.x("UPDATE inventions SET opinion=?, updated=? WHERE id=?", (opinion, now, iid))
        if i["item_id"]:
            db.x("UPDATE habitat SET story=? WHERE id=?", (_story(i, opinion), i["item_id"]))
        db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
             (now, f"What I think of my {i['name']}: {opinion}", 3, "invention"))
        return "Noted. Your opinion is part of its story now: visitors can read it when they click it."
    if body.get("energy", 0) < 8:
        return "Too tired to work on an invention. Rest first."
    gap = SESSION_GAP_HOURS * 3600 / max(config.TIME_SCALE, 1e-6)
    if i["last_session"] and now - i["last_session"] < gap:
        return (f"You worked on the {i['name']} not long ago and your paws need a rest from it. Come back to it in a "
                "few hours: good inventions take a few days.")
    sessions = i["sessions"] + 1
    stamp = time.strftime("%b %d", time.localtime(now))
    log = (i["log"] + f"\n[{stamp}] {note or 'worked on it'}").strip()[-3000:]
    body["energy"] = max(0.0, body.get("energy", 50) - 6)
    body["fun"] = min(100.0, body.get("fun", 50) + 5)
    body["activity"] = f"working on his invention: the {i['name']}"
    if sessions < i["needed"]:
        db.x("UPDATE inventions SET sessions=?, last_session=?, log=?, status='building', updated=? WHERE id=?",
             (sessions, now, log, now, iid))
        db.event("build", f"worked on his invention, the {i['name']} (session {sessions})")
        left = i["needed"] - sessions
        return (f"Session {sessions} on the {i['name']} done. It's coming along: about {left} more session"
                f"{'s' if left > 1 else ''} to go, after a rest.")
    # finished!
    twist, change = random.choice(TWISTS) if random.random() < TWIST_CHANCE else ("", {})
    kind = change.get("kind") or i["kind"]
    size = change.get("size", 1.0)
    color = random.choice(COLOURS) if change.get("recolour") else ""
    pos = body.get("pos") or [7, 5]
    x, y = (a["x"], a["y"]) if a.get("x") is not None and a.get("y") is not None else pos
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        x, y = pos
    done = {**i, "sessions": sessions, "twist": twist}
    placed = keepsakes.place(i["name"], i["emoji"], x, y, kind=kind, color=color, size=size,
                             description="A dream invention", story=_story(done), origin=f"invention:{iid}")
    if not placed:
        return "Your home is full: there's nowhere to put it. Move or remove something first."
    db.x("UPDATE inventions SET sessions=?, last_session=?, log=?, status='built', twist=?, item_id=?, updated=? "
         "WHERE id=?", (sessions, now, log, twist, placed[0], now, iid))
    body["pos"] = [placed[1], placed[2]]
    body["fun"] = min(100.0, body["fun"] + 10)
    body["activity"] = f"admiring his new {i['name']}"
    db.event("build", f"finished his dream invention, the {i['name']}")
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (now, f"I built the {i['name']} I dreamed of" + (f", but {twist}." if twist else ", just like the dream."),
          4, "invention"))
    out = f"You finished the {i['name']}! It stands at ({placed[1]},{placed[2]}) (item #{placed[0]})."
    if twist:
        out += (f" But it didn't come out like the dream: {twist}. How do you feel about that? Say what you think "
                "with work_on_invention and an opinion (it becomes part of its story).")
    else:
        out += " It came out just like the dream. What do you think of it? (work_on_invention with an opinion)"
    return out


def context_lines(now: float | None = None) -> str:
    now = now or time.time()
    rows = db.q("SELECT * FROM inventions WHERE status IN ('dreamed','building') OR "
                "(status='built' AND opinion='' AND updated>?) ORDER BY ts DESC LIMIT 4", (now - 3 * DAY,))
    if not rows:
        return ""
    out = ["\n## Your dream inventions"]
    for i in rows:
        if i["status"] == "built":
            out.append(f"- #{i['id']} the {i['name']}: built! You haven't said what you think of it yet.")
            continue
        sketch = "sketched" if i["sketch_id"] else "not sketched yet"
        rest = ""
        if i["last_session"] and now - i["last_session"] < SESSION_GAP_HOURS * 3600 / max(config.TIME_SCALE, 1e-6):
            rest = " (resting from it for now)"
        out.append(f"- #{i['id']} the {i['name']}: {i['idea'][:160]} [{sketch}, {i['sessions']} of about "
                   f"{i['needed']} work sessions{rest}]")
    return "\n".join(out)


def public_story(origin: str, item: dict) -> str:
    try:
        iid = int(origin.split(":", 1)[1])
    except (IndexError, ValueError):
        return keepsakes.PRIVATE_STORY
    rows = db.q("SELECT * FROM inventions WHERE id=?", (iid,))
    if not rows:
        return keepsakes.PRIVATE_STORY
    i = rows[0]
    safe = lambda t: t if t and not public.check(t) else ""  # noqa: E731
    parts = [f"Gino dreamed this up on {keepsakes.when(i['ts'])}" + (f": {safe(i['idea'])}" if safe(i["idea"]) else ".")]
    parts.append(f"He built it over {i['sessions']} work sessions.")
    if i["twist"]:
        parts.append(f"It didn't come out quite as dreamed: {i['twist']}.")
    if safe(i["opinion"]):
        parts.append(f"What Gino thinks of it: “{i['opinion']}”")
    return re.sub(r"\.\.", ".", " ".join(parts))[:1200]
