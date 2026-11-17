"""Gino's dreams. While he sleeps through the night his mind shuffles his memories into a dream.

How it works:
- When Gino goes to sleep for a while (2 hours or more), a dream is planned for part-way through that sleep.
- At that moment his memories, his day, his goals and how his body feels are mixed into a dream with one
  Claude call (about 5 US cents). Some nights the dream is ordinary, some nights strange, and now and then it
  is a full-blown "vision": surreal and impossible, like a hallucination.
- The dream is saved, it changes how he feels when he wakes up, and it becomes a memory.
- His first turn after waking starts with the dream. He decides what to do with it: paint it (his painting
  is linked to the dream), write about it, let it change what he wants, or just shrug.
- For a day or so afterwards, bits of the dream can flicker back, especially when he's very tired.

Dreams are private like his diary. They only reach his website if he chooses to publish something, and that
still goes through the privacy check in public.py.
"""
import json
import logging
import random
import time

from . import config, db, vitals

log = logging.getLogger("gino.dreams")

# How strange tonight's dream is. 1 = replaying the day, 5 = a vision where nothing obeys the rules.
STRANGENESS = {
    1: "Calm and close to real life: replaying bits of the day, only slightly off.",
    2: "Mostly familiar, but things blend: places merge, people and objects swap, time skips.",
    3: "Properly dreamlike: impossible sizes, talking things, places that are two places at once.",
    4: "Very strange: the rules of the world bend. Gravity, colours, time and your own body behave oddly.",
    5: "A VISION, like a hallucination. Surreal, vivid and symbolic: the sky could open, the meadow could fold "
       "like paper, you could be enormous or tiny or made of something else. It should feel unforgettable.",
}

DREAM_TOOL = {
    "name": "dream",
    "description": "Record the dream you are having tonight.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short name for the dream, like a painting's title"},
            "story": {"type": "string", "description": "The dream itself, told in first person, present tense, "
                      "as you experience it. 90 to 220 words. Dream logic, not a neat story."},
            "symbols": {"type": "array", "items": {"type": "string"}, "description": "3 to 6 of the most vivid "
                        "images from it, a few words each (e.g. 'a pond full of stars')"},
            "colours": {"type": "string", "description": "The colours and light of the dream, for painting it later"},
            "feeling": {"type": "string", "description": "One word for how you feel when you wake up"},
            "intensity": {"type": "integer", "description": "How strongly, 1 to 5"},
            "longing": {"type": "string", "description": "What the dream leaves you wanting, wondering or "
                        "afraid of, in one sentence. Or 'nothing' if it was just a dream."},
            "sources": {"type": "string", "description": "Which real memories it seems to come from (your guess)"},
        },
        "required": ["title", "story", "symbols", "feeling", "longing"],
    },
}


def enabled() -> bool:
    return config.DREAMS_ON


# ---------------------------------------------------------------- scheduling (called from vitals / server)

def plan(body: dict, hours: float) -> None:
    """Gino is going to sleep for `hours`. Plan a dream for somewhere in the middle of it."""
    body.pop("dream_due", None)
    if not enabled() or hours < config.DREAM_MIN_SLEEP_HOURS:
        return
    last = db.q("SELECT ts FROM dreams ORDER BY ts DESC LIMIT 1")
    if last and time.time() - last[0]["ts"] < 8 * 3600:  # one dream a night is plenty
        return
    body["dream_due"] = time.time() + hours * 3600 / config.TIME_SCALE * random.uniform(0.45, 0.85)


def due(body: dict, now: float | None = None) -> bool:
    now = now or time.time()
    return bool(body.get("dream_due")) and vitals.is_asleep(body, now) and now >= body["dream_due"]


# ---------------------------------------------------------------- what the dream is made of

def _pick_strangeness(body: dict) -> int:
    """Mostly ordinary or a bit odd; a vision now and then. Exhaustion and big feelings make dreams stranger."""
    weights = [20, 30, 27, 13, 10]
    if body.get("energy", 50) < 20 or body.get("emotion_intensity", 3) >= 5:
        weights = [10, 22, 30, 20, 18]
    return random.choices([1, 2, 3, 4, 5], weights=weights)[0]


def fragments(body: dict) -> dict:
    """Pieces of his life for the dream to be built from: some from today, some from long ago."""
    day_ago = time.time() - 24 * 3600
    today = db.q("SELECT text FROM events WHERE ts>? AND kind NOT IN ('turn','mind','sleep','dream') ORDER BY RANDOM() LIMIT 10",
                 (day_ago,))
    old = db.q("SELECT text FROM memories ORDER BY (ABS(RANDOM()) % 100) * importance DESC LIMIT 4")
    recent = db.q("SELECT text FROM memories ORDER BY ts DESC LIMIT 3")
    made = db.q("SELECT kind,title FROM creations ORDER BY RANDOM() LIMIT 2")
    goals = db.q("SELECT title FROM goals WHERE status='active' ORDER BY RANDOM() LIMIT 2")
    home = db.q("SELECT name FROM habitat ORDER BY RANDOM() LIMIT 4")
    chat = db.q("SELECT sender,text FROM chat WHERE ts>? ORDER BY RANDOM() LIMIT 2", (day_ago - 2 * 86400,))
    prev = db.q("SELECT title,symbols FROM dreams ORDER BY ts DESC LIMIT 1")
    me = db.get("self", {})
    v = vitals.snapshot(body)
    needs = [word for n, word in (("fullness", "hungry"), ("social", "lonely"), ("fun", "bored"),
                                  ("comfort", "uncomfortable")) if v[n] < 30]
    return {
        "today": [r["text"][:200] for r in today],
        "memories": list(dict.fromkeys(r["text"][:300] for r in old + recent)),
        "creations": [f"{r['kind']}: {r['title']}" for r in made],
        "goals": [r["title"] for r in goals],
        "home": [r["name"] for r in home],
        "chat": [f"{'Dad' if r['sender'] == 'dad' else 'You'}: {r['text'][:200]}" for r in chat],
        "self": {k: str(val)[:200] for k, val in me.items()},
        "body": needs,
        "feeling": f"{body.get('emotion')} ({body.get('emotion_intensity')}/5): {body.get('emotion_reason')}",
        "recurring": (prev[0] if prev and random.random() < 0.15 else None),
    }


def prompt(body: dict, level: int, f: dict) -> str:
    def block(title, items):
        return f"\n{title}:\n" + ("\n".join(f"- {i}" for i in items) if items else "- (nothing)")
    parts = [
        "You are fast asleep in your meadow. You are dreaming.",
        "Below are fragments floating around your sleeping mind. A dream takes a few of them (not all!) and "
        "mixes, swaps and transforms them the way real dreams do: a creation becomes a place, a goal becomes a "
        "journey, someone from a chat turns up somewhere they shouldn't be, a feeling becomes weather.",
        f"\nTonight's dream: {STRANGENESS[level]}",
        block("Things that happened in the last day", f["today"]),
        block("Memories surfacing (some old, some new)", f["memories"]),
        block("Things you've made", f["creations"]),
        block("Things you are working towards", f["goals"]),
        block("Things in your home", f["home"]),
        block("Bits of conversation", f["chat"]),
        block("Who you are", [f"{k}: {v}" for k, v in f["self"].items()]),
        f"\nHow you felt falling asleep: {f['feeling']}",
    ]
    if f["body"]:
        parts.append("Your body is " + ", ".join(f["body"]) + ", and that leaks into the dream.")
    if f["recurring"]:
        parts.append(f"A dream you had before is coming back, changed: \"{f['recurring']['title']}\".")
    parts.append(
        "\nDreams can be joyful, funny, tender, eerie or a little unsettling, like real dreams. Keep them "
        "gentle enough for a young capybara: no gore or cruelty. Don't explain the dream inside it. "
        "Call the dream tool once to record it (don't write anything else).")
    return "\n".join(parts)


# ---------------------------------------------------------------- having the dream

def dream_now() -> int | None:
    """Gino dreams. Returns the new dream's id (or None if he slept soundly)."""
    from . import brain  # late import: brain imports this module
    with brain.mind_lock:
        body = vitals.tick(vitals.load())
        if not due(body):
            return None
        body.pop("dream_due", None)
        vitals.save(body)
        level = _pick_strangeness(body)
        f = fragments(body)
        text = prompt(body, level, f)
        max_tokens = 4000
        if not config.FAKE_BRAIN:  # the dream must fit in what's left of today's budget, worst case included
            from . import budget
            est = budget.estimate_tokens(brain.SYSTEM, text, [DREAM_TOOL])
            max_tokens = budget.step_allowance(config.DREAM_MODEL, brain.spent_today(), "dream", est, want=4000)
        if (config.FAKE_BRAIN and brain.spent_today() >= config.DAILY_BUDGET_USD) or not max_tokens:
            db.event("sleep", "Gino slept too deeply to dream (thinking budget used up for today).")
            return None
        if config.FAKE_BRAIN:
            d = fake_dream(f, level)
        else:
            d = _ask_claude(brain, text, max_tokens)
            if not d:
                return None
        return save(body, d, level)


def _ask_claude(brain, text: str, max_tokens: int = 4000) -> dict | None:
    # Newer models don't allow forcing a tool, so the prompt asks for it; plain text still counts as a dream.
    resp = brain.call(config.DREAM_MODEL, [{"role": "user", "content": text}], [DREAM_TOOL], max_tokens=max_tokens)
    brain.record_spend("dream", resp, config.DREAM_MODEL)
    for b in resp.content:
        if b.type == "tool_use" and b.name == "dream" and isinstance(b.input, dict) and b.input.get("story"):
            return b.input
    said = " ".join(b.text for b in resp.content if b.type == "text").strip()
    if resp.stop_reason != "refusal" and len(said) > 80:
        return {"title": "A dream I can't name", "story": said, "symbols": [], "feeling": "dreamy", "longing": ""}
    db.event("sleep", "Gino slept soundly and doesn't remember dreaming.")
    return None


def _txt(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def save(body: dict, d: dict, level: int) -> int:
    now = time.time()
    symbols = d.get("symbols") or []
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(",")]
    symbols = [_txt(s, 80) for s in symbols if _txt(s, 80)][:6]
    title = _txt(d.get("title"), 80) or "A dream"
    story = str(d.get("story") or "").strip()[:3000]
    feeling = _txt(d.get("feeling"), 30).lower() or "dreamy"
    try:
        intensity = max(1, min(int(d.get("intensity") or 3), 5))
    except (TypeError, ValueError):
        intensity = 3
    longing = _txt(d.get("longing"), 300)
    did = db.x("INSERT INTO dreams(ts,title,story,symbols,colours,feeling,intensity,longing,sources,strangeness) "
               "VALUES(?,?,?,?,?,?,?,?,?,?)",
               (now, title, story, json.dumps(symbols), _txt(d.get("colours"), 300), feeling, intensity, longing,
                _txt(d.get("sources"), 400), level))
    # The dream colours how he feels when he wakes up, and he'll remember it.
    body["emotion"], body["emotion_intensity"] = feeling, intensity
    body["emotion_reason"] = f"still half inside a dream: {title}"
    body["thought"] = (symbols[0] + "...") if symbols else "What a strange dream..."
    body["fun"] = vitals.clamp(body["fun"] + 2 + level)
    body["fresh_dream"] = did
    body["last_dream_ts"] = now
    vitals.save(body)
    keep = f"I dreamed '{title}'." + (f" Afterwards: {longing}" if longing and longing.lower() != "nothing" else "")
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (now, keep[:1000], 4 if level == 5 else 3, "dream"))
    db.event("dream", ("had a vision in his sleep: " if level == 5 else "dreamed: ") + title)
    return did


# ---------------------------------------------------------------- what Gino sees when awake

def _symbols(r: dict) -> list[str]:
    try:
        return [s for s in json.loads(r.get("symbols") or "[]") if s]
    except ValueError:
        return []


def get(did: int) -> dict | None:
    rows = db.q("SELECT * FROM dreams WHERE id=?", (did,))
    return rows[0] if rows else None


def waking_lines(did: int) -> str:
    """The start of his first turn after a dream."""
    d = get(did)
    if not d:
        return ""
    kind = "a vision, the strangest kind of dream" if d["strangeness"] == 5 else "a dream"
    lines = [f"## You just woke up from {kind} (dream #{d['id']})",
             f"**{d['title']}**", d["story"],
             "Vivid images: " + "; ".join(_symbols(d)),
             f"Its colours: {d['colours']}" if d["colours"] else "",
             f"You woke up feeling {d['feeling']}. " + (f"It left you with this: {d['longing']}"
                                                         if d["longing"] and d["longing"].lower() != "nothing" else ""),
             "\nThe dream is yours to do with as you like. Dreams fade fast, so many mornings you like to paint "
             f"yours before it's gone: use create with kind 'svg' and dream_id {d['id']}. A dream painting doesn't "
             "need to look like real life: impossible sizes, floating things, colours that glow or don't match, "
             "soft gradients, blur and turbulence filters (<feGaussianBlur>, <feTurbulence>), things melting into "
             "each other. You could also write it in your diary, put the painting on your website, or tell dad. "
             "If it left you wanting something, let it change you if it feels true: update_self (your dreams or "
             "passions) or set_goal. Or shrug it off: not every dream means something."]
    return "\n".join(x for x in lines if x)


def context_lines(body: dict) -> str:
    """Recent dreams in his everyday view, plus the odd flicker of one when he's tired."""
    rows = db.q("SELECT * FROM dreams ORDER BY ts DESC LIMIT 3")
    if not rows:
        return ""
    from .brain import ago
    out = ["\n## Your recent dreams"]
    for r in rows:
        painted = " (you painted it)" if r["creation_id"] else ""
        want = f" It left you: {r['longing']}" if r["longing"] and r["longing"].lower() != "nothing" else ""
        out.append(f"- #{r['id']} ({ago(r['ts'])}) {r['title']}{painted}: {r['story'][:220]}...{want}")
    echo = _echo(body, rows)
    if echo:
        out.append(echo)
    return "\n".join(out)


def _echo(body: dict, rows: list[dict]) -> str:
    """A waking flicker: tired eyes, or the morning after a vision, make dream images come back for a moment."""
    fresh = [r for r in rows if time.time() - r["ts"] < 30 * 3600]
    if not fresh:
        return ""
    r = fresh[0]
    chance = 0.0
    if body.get("energy", 50) < 20:
        chance += 0.6
    if r["strangeness"] >= 4:
        chance += 0.25
    syms = _symbols(r)
    if not syms or random.random() >= chance:
        return ""
    home = db.q("SELECT name FROM habitat ORDER BY RANDOM() LIMIT 1")
    where = f"near your {home[0]['name']}" if home else "at the edge of the meadow"
    return (f"\nFor a second just now you were sure you saw {random.choice(syms)} {where}. You blinked and it "
            f"was gone. Was it the dream '{r['title']}' leaking into the day?")


def link_painting(dream_id, creation_id: int) -> str:
    try:
        did = int(dream_id)
    except (TypeError, ValueError):
        return ""
    if not get(did):
        return ""
    db.x("UPDATE creations SET dream_id=? WHERE id=?", (did, creation_id))
    db.x("UPDATE dreams SET creation_id=? WHERE id=?", (creation_id, did))
    db.event("dream", f"painted his dream #{did}")
    return f" It's linked to dream #{did}."


# ---------------------------------------------------------------- practice brain (no API key)

def fake_dream(f: dict, level: int) -> dict:
    """A simple dream made from his own fragments, so dreaming works without an API key."""
    pool = list(dict.fromkeys(f["home"] + f["goals"] + ["a watermelon", "the moon", "a sunflower"]))
    a, b = random.sample(pool, 2) if len(pool) >= 2 else ("the pond", "the moon")
    twist = {1: "and everything was just how it is", 2: "but it was also somehow the forest",
             3: "and it started talking to me in a slow, kind voice", 4: "and I was floating upside down above it",
             5: "and the whole meadow folded up like paper with me inside"}[level]
    return {"title": f"The dream of {a}", "symbols": [a, b, "warm light"], "feeling": "dreamy", "intensity": 3,
            "story": f"I'm walking towards {a}, {twist}. Then {b} is there too, much bigger than it should be. "
                     "I sit and watch it for a long time. It feels important but I don't know why.",
            "colours": "soft blues and gold", "longing": f"I want to understand why I dreamed of {a}.",
            "sources": "today"}
