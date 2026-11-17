"""Time capsules: now and then Gino buries a letter to future Gino, and digs it up weeks later.

Inside: a drawing (optional), his favourite thing right now, a prediction about his future and a few words to his
future self. A snapshot of his life goes in with it automatically (his interests, his projects, his art period, his
mood), so when he opens it he can see how much he has changed. The capsule is a real little mound with a marker in
his 3D world while it waits. He can't peek: it only opens on the day he chose.

No extra cost: sealing and opening happen with his own tools during ordinary turns.
"""
import json
import random
import time

from . import continuity, db, keepsakes, public

DAY = 86400
MIN_DAYS, MAX_DAYS, DEFAULT_DAYS = 14, 90, 30
GAP_DAYS = 7  # at least a week between capsules
MAX_WAITING = 2  # never more than two buried at once


def _txt(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def snapshot(body: dict) -> dict:
    """Who Gino is today, packed in automatically so future-him can compare."""
    from . import artstyle
    period = artstyle.current()
    return {
        "interests": [t["topic"] for t in continuity.interests()[:5]],
        "projects": [g["title"] for g in db.q("SELECT title FROM goals WHERE status='active' ORDER BY id LIMIT 5")],
        "art_period": period["name"] if period else "",
        "feeling": str(body.get("emotion") or ""),
        "creations": db.q("SELECT COUNT(*) AS n FROM creations")[0]["n"],
        "home": db.q("SELECT COUNT(*) AS n FROM habitat")[0]["n"],
        "age_days": round((time.time() - body.get("born", time.time())) / DAY, 1),
    }


def seal(body: dict, a: dict) -> str:
    now = time.time()
    fav, pred = _txt(a.get("favourite_thing"), 300), _txt(a.get("prediction"), 500)
    if not fav or not pred:
        return "A time capsule needs your favourite thing right now and a prediction about future you."
    waiting = db.q("SELECT id,ts FROM capsules WHERE opened IS NULL")
    if len(waiting) >= MAX_WAITING:
        return "You already have time capsules waiting in the ground. Let those open first."
    last = db.q("SELECT ts FROM capsules ORDER BY ts DESC LIMIT 1")
    if last and now - last[0]["ts"] < GAP_DAYS * DAY:
        return "You buried a capsule only a few days ago. Time capsules are special because they're rare."
    try:
        days = max(MIN_DAYS, min(int(a.get("open_in_days") or DEFAULT_DAYS), MAX_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_DAYS
    cid = None
    if a.get("creation_id") not in (None, "", 0):
        try:
            cid = int(a["creation_id"])
        except (TypeError, ValueError):
            cid = None
        if cid and not db.q("SELECT 1 FROM creations WHERE id=?", (cid,)):
            return f"You don't have a creation #{cid}."
    opens = now + days * DAY
    pos = body.get("pos") or [7, 5]
    x, y = (a.get("x"), a.get("y")) if a.get("x") is not None and a.get("y") is not None else pos
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        x, y = pos
    capsule = db.x("INSERT INTO capsules(ts,open_after,creation_id,favourite,prediction,letter,snapshot) "
                   "VALUES(?,?,?,?,?,?,?)", (now, opens, cid, fav, pred, _txt(a.get("letter"), 1500),
                                             json.dumps(snapshot(body))))
    origin = f"capsule:{capsule}"
    placed = keepsakes.place("time capsule", "🕰️", x, y, kind="capsule", origin=origin,
                             description="Something buried for later",
                             story=f"Gino buried a time capsule here on {keepsakes.when(now)}. "
                                   f"He'll dig it up around {keepsakes.when(opens)}.")
    where = ""
    if placed:
        db.x("UPDATE capsules SET item_id=? WHERE id=?", (placed[0], capsule))
        body["pos"] = [placed[1], placed[2]]
        where = f" at ({placed[1]},{placed[2]})"
    body["activity"] = "burying a time capsule"
    db.event("build", f"buried a time capsule{where}")
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (now, f"I buried time capsule #{capsule}. It opens on {keepsakes.when(opens)}. No peeking!", 3,
          "time capsule"))
    return (f"Time capsule #{capsule} is buried{where}. It will be ready to open in {days} days "
            f"({keepsakes.when(opens)}). No peeking until then!")


def _compare(then: dict, body: dict) -> str:
    now = snapshot(body)

    def row(label, a, b):
        a = ", ".join(a) if isinstance(a, list) else a
        b = ", ".join(b) if isinstance(b, list) else b
        return f"- {label}: then {a or '(nothing)'}; now {b or '(nothing)'}"
    return "\n".join([
        row("your interests", then.get("interests"), now["interests"]),
        row("your projects", then.get("projects"), now["projects"]),
        row("your art period", then.get("art_period"), now["art_period"]),
        row("how you felt", then.get("feeling"), now["feeling"]),
        f"- things you'd made: then {then.get('creations', '?')}, now {now['creations']}",
        f"- things in your home: then {then.get('home', '?')}, now {now['home']}",
    ])


def open_capsule(body: dict, a: dict) -> str:
    now = time.time()
    try:
        cid = int(a.get("capsule_id") or 0)
    except (TypeError, ValueError):
        cid = 0
    rows = db.q("SELECT * FROM capsules WHERE id=?", (cid,))
    if not rows:
        return f"There's no time capsule #{cid}."
    c = rows[0]
    reflection = _txt(a.get("reflection"), 1500)
    text = ""
    if c["opened"] is None:
        if now < c["open_after"]:
            return (f"Not yet! You promised yourself to wait until {keepsakes.when(c['open_after'])}. "
                    "The waiting is part of it.")
        db.x("UPDATE capsules SET opened=? WHERE id=?", (now, cid))
        body["activity"] = "digging up an old time capsule"
        body["fun"] = min(100.0, body.get("fun", 50) + 8)
        db.event("build", f"dug up time capsule #{cid}")
        drawing = ""
        if c["creation_id"]:
            d = db.q("SELECT title FROM creations WHERE id=?", (c["creation_id"],))
            drawing = f"\n- The drawing you put in: '{d[0]['title']}' (creation #{c['creation_id']})" if d else ""
        then = json.loads(c["snapshot"] or "{}")
        text = (f"You dig up time capsule #{cid}, buried on {keepsakes.when(c['ts'])} "
                f"({int((now - c['ts']) // DAY)} days ago). Inside:\n"
                f"- Your favourite thing back then: {c['favourite']}\n"
                f"- Your prediction: \"{c['prediction']}\"{drawing}\n"
                + (f"- Your letter to future you: \"{c['letter']}\"\n" if c["letter"] else "")
                + f"\nThen and now:\n{_compare(then, body)}\n\n"
                "Take a moment. Did your prediction come true? What changed, what stayed the same? How does it feel "
                "to meet past you? When you're ready, call open_time_capsule again with your reflection.")
        if not reflection:
            return text
    if not reflection:
        return f"You already opened capsule #{cid}. Add your thoughts with a reflection if you like."
    db.x("UPDATE capsules SET reflection=? WHERE id=?", (reflection, cid))
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (now, f"I opened a time capsule from {keepsakes.when(c['ts'])}. I had predicted: \"{c['prediction']}\". "
               f"Looking back: {reflection}"[:1000], 4, "time capsule"))
    if c["item_id"]:
        db.x("UPDATE habitat SET name=?, emoji=?, story=? WHERE id=?",
             ("opened time capsule", "📜",
              f"Gino buried a time capsule here on {keepsakes.when(c['ts'])} and dug it up on "
              f"{keepsakes.when(c['opened'] or now)}. His favourite thing back then: {c['favourite']}. "
              f"He had guessed: \"{c['prediction']}\". When he opened it he said: \"{reflection}\"", c["item_id"]))
    db.event("memory", f"reflected on time capsule #{cid}")
    return (text + "\n\n" if text else "") + ("Your reflection is kept with the capsule, and anyone who finds the "
                                               "spot in your meadow can read it.")


def public_story(origin: str, item: dict) -> str:
    """The capsule's marker story for visitors: dates always, his own words only if they pass the privacy check."""
    try:
        cid = int(origin.split(":", 1)[1])
    except (IndexError, ValueError):
        return keepsakes.PRIVATE_STORY
    rows = db.q("SELECT * FROM capsules WHERE id=?", (cid,))
    if not rows:
        return keepsakes.PRIVATE_STORY
    c = rows[0]
    if c["opened"] is None:
        return (f"Gino buried a time capsule here on {keepsakes.when(c['ts'])}. Inside: a letter to his future self. "
                f"He'll dig it up around {keepsakes.when(c['open_after'])}.")
    parts = [f"Gino buried a time capsule here on {keepsakes.when(c['ts'])} and dug it up on "
             f"{keepsakes.when(c['opened'])}."]
    for words, said in ((c["favourite"], "His favourite thing back then: {}."),
                        (c["prediction"], "He had guessed: “{}.”"),
                        (c["reflection"], "When he opened it he said: “{}.”")):
        if words and not public.check(words):
            parts.append(said.format(words.rstrip(".!? ")) if said.endswith(".") or words[-1:] not in "!?"
                         else said.replace(".”", "”").format(words.strip()))
    return " ".join(parts)[:1200]


def context_lines(body: dict, now: float | None = None) -> str:
    now = now or time.time()
    out = []
    for c in db.q("SELECT id,ts,open_after,opened,reflection FROM capsules WHERE opened IS NULL OR reflection='' "
                  "ORDER BY ts"):
        if c["opened"] is not None:
            out.append(f"- You opened capsule #{c['id']} but haven't said what you thought (open_time_capsule "
                       "with a reflection).")
        elif now >= c["open_after"]:
            out.append(f"- 🕰️ Time capsule #{c['id']}, buried {int((now - c['ts']) // DAY)} days ago, is READY to "
                       "dig up. Open it with open_time_capsule whenever you like.")
        else:
            out.append(f"- Capsule #{c['id']} is buried; it opens in {max(1, round((c['open_after'] - now) / DAY))} "
                       "days. You can't peek.")
    if out:
        return "\n## Time capsules\n" + "\n".join(out)
    age = (now - body.get("born", now)) / DAY
    last = db.q("SELECT ts FROM capsules ORDER BY ts DESC LIMIT 1")
    if age >= 2 and (not last or now - last[0]["ts"] > 21 * DAY) and random.random() < 0.12:
        return ("\n## An idea\nYou could bury a time capsule for future you (seal_time_capsule): your favourite thing "
                "right now, a guess about who you'll be in a few weeks, maybe a drawing. Only if you feel like it.")
    return ""
