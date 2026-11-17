"""Gino's body: needs that drift over time, food, sleep and mood."""
import datetime as dt
import hashlib
import random
import time

from . import config, db

NEEDS = ("fullness", "energy", "social", "fun", "comfort")

# Change per real hour while awake / asleep.
AWAKE_DRIFT = {"fullness": -5, "energy": -4, "social": -3, "fun": -4}
ASLEEP_DRIFT = {"fullness": -2, "energy": +14, "social": -1, "fun": 0}

FOODS = {
    # name: (fullness, fun, emoji)
    "grass": (8, 0, "🌿"), "hay": (10, -1, "🌾"), "lettuce": (9, 1, "🥬"),
    "corn": (14, 3, "🌽"), "sweet potato": (18, 3, "🍠"), "apple": (12, 4, "🍎"),
    "pumpkin": (20, 4, "🎃"), "watermelon": (16, 9, "🍉"), "carrot": (11, 3, "🥕"),
    "melon": (15, 7, "🍈"),
}
FORAGE_POOL = ["grass"] * 6 + ["hay"] * 3 + ["lettuce"] * 2 + ["carrot", "corn", "apple"]
GARDEN_POOL = ["sweet potato", "pumpkin", "watermelon", "corn", "melon", "carrot", "lettuce"]

DEFAULT = {
    "fullness": 70, "energy": 80, "social": 60, "fun": 60, "comfort": 30,
    "emotion": "curious", "emotion_intensity": 3, "emotion_reason": "Just woke up in a brand new world.",
    "thought": "Where am I? It smells like grass. I like it already.",
    "activity": "looking around", "asleep_until": 0, "next_wake": 0,
    "pantry": {"grass": 3, "watermelon": 1}, "pos": [7, 5], "born": 0, "last_update": 0,
}


def clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def load() -> dict:
    s = db.get("body")
    if s is None:
        s = dict(DEFAULT)
        now = time.time()
        s["born"] = s["last_update"] = s["next_wake"] = now
        db.put("body", s)
        db.event("life", "Gino was born.")
    return s


def save(s: dict) -> None:
    db.put("body", s)


def is_asleep(s: dict, now: float | None = None) -> bool:
    return s.get("asleep_until", 0) > (now or time.time())


def comfort_from_habitat() -> float:
    items = db.q("SELECT name FROM habitat")
    names = " ".join(i["name"].lower() for i in items)
    score = 15 + min(len(items), 20) * 3.5
    for word, bonus in (("pond", 12), ("pool", 12), ("water", 8), ("bed", 8), ("shade", 5), ("tree", 4)):
        if word in names:
            score += bonus
    return clamp(score)


def tick(s: dict, now: float | None = None) -> dict:
    """Advance needs from last_update to now."""
    now = now or time.time()
    hours = max(0.0, now - s.get("last_update", now)) / 3600 * config.TIME_SCALE
    if hours <= 0:
        return s
    asleep = is_asleep(s, now)
    drift = ASLEEP_DRIFT if asleep else AWAKE_DRIFT
    for k, per_hour in drift.items():
        s[k] = clamp(s[k] + per_hour * hours)
    s["comfort"] = round(0.8 * s.get("comfort", 30) + 0.2 * comfort_from_habitat(), 2)
    if s["fullness"] < 15 and asleep:  # hunger wakes him up
        s["asleep_until"] = now
        db.event("body", "Gino's tummy rumbled so loudly he woke up.")
    if s["energy"] < 3 and not asleep:
        s["asleep_until"] = now + 3 * 3600 / config.TIME_SCALE
        s["activity"] = "collapsed into a nap"
        db.event("body", "Gino was too tired and fell asleep where he stood.")
    if not asleep and s.get("activity") in ("sleeping", "napping"):
        s["activity"] = "just woke up"
    s["last_update"] = now
    return s


def mood(s: dict) -> int:
    """0-100 overall mood: needs plus how he says he feels."""
    base = (s["fullness"] * 1.2 + s["energy"] + s["social"] * 1.1 + s["fun"] + s["comfort"] * 0.7) / 5.0
    positive = {"happy", "joyful", "excited", "content", "proud", "peaceful", "loved", "playful",
                "curious", "grateful", "inspired", "calm", "cozy"}
    negative = {"sad", "lonely", "bored", "angry", "anxious", "frustrated", "scared", "grumpy", "tired"}
    e = s.get("emotion", "").lower()
    inten = s.get("emotion_intensity", 3)
    if e in positive:
        base += inten * 2
    elif e in negative:
        base -= inten * 2
    return int(clamp(base))


def forage(s: dict) -> str:
    if s["energy"] < 8:
        return "Too tired to forage. Sleep first."
    has_garden = bool(db.q("SELECT 1 FROM habitat WHERE lower(name) LIKE '%garden%' LIMIT 1"))
    found = random.choices(FORAGE_POOL, k=random.randint(1, 3))
    if has_garden:
        found += random.choices(GARDEN_POOL, k=random.randint(1, 2))
    for f in found:
        s["pantry"][f] = s["pantry"].get(f, 0) + 1
    s["energy"] = clamp(s["energy"] - 6)
    s["fun"] = clamp(s["fun"] + 2)
    s["activity"] = "foraging"
    note = " (your garden helped!)" if has_garden else ""
    return f"Found: {', '.join(found)}{note}. Pantry now: {s['pantry']}"


def eat(s: dict, food: str, amount: int = 1) -> str:
    food = food.lower().strip()
    have = s["pantry"].get(food, 0)
    if have <= 0:
        return f"No {food} in the pantry. Pantry: {s['pantry']}"
    amount = max(1, min(amount, have))
    full, fun, _ = FOODS.get(food, (10, 1, "🍽️"))
    s["fullness"] = clamp(s["fullness"] + full * amount)
    s["fun"] = clamp(s["fun"] + fun * amount)
    s["pantry"][food] = have - amount
    if s["pantry"][food] == 0:
        del s["pantry"][food]
    s["activity"] = f"munching {food}"
    msg = f"Ate {amount} {food}. Fullness {s['fullness']:.0f}/100."
    if s["fullness"] >= 100:
        msg += " Very, very full."
    return msg


def sleep(s: dict, hours: float) -> str:
    hours = max(0.25, min(hours, 10))
    s["asleep_until"] = time.time() + hours * 3600 / config.TIME_SCALE
    s["next_wake"] = s["asleep_until"]
    s["slept_at"] = time.time()
    s["activity"] = "sleeping"
    from . import dreams  # late import: dreams imports this module
    dreams.plan(s, hours)
    return f"Going to sleep for {hours:g} hours. Zzz." + (" Maybe you'll dream." if s.get("dream_due") else "")


def snapshot(s: dict) -> dict:
    out = {k: round(s[k]) for k in NEEDS}
    out["mood"] = mood(s)
    return out


def season(now: dt.datetime) -> str:
    names = ["winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn",
             "autumn", "winter"]
    s = names[now.month - 1]
    if config.HEMISPHERE == "south":
        s = {"winter": "summer", "summer": "winter", "spring": "autumn", "autumn": "spring"}[s]
    return s


def weather(now: dt.datetime) -> dict:
    """The sky over Gino's world. Changes every three hours, the same for everyone looking."""
    s = season(now)
    block = f"{now:%Y-%m-%d}-{now.hour // 3}"
    roll = int(hashlib.sha256(block.encode()).hexdigest()[:8], 16) % 100
    table = {"spring": (50, 72, 92), "summer": (66, 84, 95), "autumn": (42, 68, 88), "winter": (40, 66, 88)}[s]
    kind = "clear" if roll < table[0] else "cloudy" if roll < table[1] else "rain" if roll < table[2] else "fog"
    if kind == "rain" and s == "winter":
        kind = "snow"
    words = {"clear": "clear skies", "cloudy": "cloudy", "rain": "raining", "snow": "snowing", "fog": "foggy"}[kind]
    return {"kind": kind, "season": s, "text": f"{words}, {s}"}
