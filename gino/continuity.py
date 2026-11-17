"""Making Gino's days add up: lasting interests, old memories that come back when they matter, and projects
that run over several days.

Nothing here costs money: it only decides which bits of his own past Gino gets to see each turn.

- Interests grow out of the topics he tags his memories with. A topic he keeps coming back to over several days
  becomes a "lasting interest"; one he hasn't touched for a while shows up as something he may want to return to.
- Older memories that connect to what he's doing now (his active projects and his interests) are pulled back
  into view, even if they are weeks old and would otherwise have scrolled away.
- Every so often one older memory simply surfaces, the way memories do.
- Projects (goals) show how long he's been at them and when he last worked on them.
"""
import random
import re
import time

from . import db

STOP = set("""about after again also always another around because been before being best better between both
could does doing done down each even ever every first from going good have having here into just keep know
last like little long look made make many maybe more most much myself need never next nice only other over
really should since some something still such sure than that their them then there these thing things think
this those through today together tomorrow very want were what when where which while will with would your
yours really maybe dad's gino gino's""".split())
DAY = 86400


def topics(tags: str) -> list[str]:
    """'Astronomy, the moon; telescopes' -> ['astronomy', 'the moon', 'telescopes']"""
    out = []
    for t in re.split(r"[,;#/|\n]+", (tags or "").lower()):
        t = " ".join(re.findall(r"[\w'-]+", t))
        if 2 <= len(t) <= 40 and t not in out:
            out.append(t)
    return out


def _ago(ts: float, now: float) -> str:
    d = (now - ts) / DAY
    if d < 1:
        return "today"
    if d < 2:
        return "yesterday"
    return f"{int(d)} days ago"


def interests(now: float | None = None, limit: int = 8) -> list[dict]:
    """His interests, strongest first. Strength grows with how often, how importantly and over how many
    different days a topic came up, and slowly fades if he leaves it alone."""
    now = now or time.time()
    by_topic: dict[str, dict] = {}
    for m in db.q("SELECT ts,importance,tags FROM memories WHERE tags!='' ORDER BY ts DESC LIMIT 3000"):
        for t in topics(m["tags"]):
            it = by_topic.setdefault(t, {"topic": t, "count": 0, "first": m["ts"], "last": m["ts"],
                                         "days": set(), "score": 0.0})
            it["count"] += 1
            it["first"], it["last"] = min(it["first"], m["ts"]), max(it["last"], m["ts"])
            it["days"].add(int(m["ts"] // DAY))
            age_days = (now - m["ts"]) / DAY
            it["score"] += m["importance"] * (0.5 ** (age_days / 21))  # a memory's weight halves every 3 weeks
    out = []
    for it in by_topic.values():
        it["n_days"] = len(it.pop("days"))
        it["score"] *= 1 + 0.4 * (it["n_days"] - 1)  # coming back on different days is what makes a passion
        if it["count"] >= 2:
            out.append(it)
    out.sort(key=lambda i: i["score"], reverse=True)
    return out[:limit]


def _keywords(*texts: str) -> set[str]:
    words = set()
    for t in texts:
        for w in re.findall(r"[a-zA-Z][a-zA-Z'-]{3,}", t or ""):
            w = w.lower().strip("'-")
            if w not in STOP:
                words.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return words


def connected_memories(goals: list[dict], tops: list[dict], exclude: set[int], limit: int = 6) -> list[dict]:
    """Older memories that connect to his active projects or his interests, best matches first."""
    want = _keywords(*(f"{g['title']} {g.get('steps', '')}" for g in goals)) | {t["topic"] for t in tops[:4]}
    if not want:
        return []
    scored = []
    for m in db.q("SELECT id,ts,text,importance,tags FROM memories ORDER BY ts DESC LIMIT 3000"):
        if m["id"] in exclude:
            continue
        have = _keywords(m["text"]) | set(topics(m["tags"]))
        hits = len(want & have)
        if hits:
            scored.append((hits * 2 + m["importance"], m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def surfacing_memory(exclude: set[int], now: float | None = None) -> dict | None:
    """Now and then an older memory just comes back to him (about one turn in three)."""
    now = now or time.time()
    if random.random() > 0.35:
        return None
    rows = [r for r in db.q("SELECT id,ts,text,importance FROM memories WHERE importance>=3 AND ts<? "
                            "ORDER BY RANDOM() LIMIT 8", (now - 2 * DAY,)) if r["id"] not in exclude]
    return rows[0] if rows else None


def goal_line(g: dict, now: float | None = None) -> str:
    """'started 4 days ago, last worked on yesterday'"""
    now = now or time.time()
    started = _ago(g["ts"], now)
    if not g.get("progress"):
        return f"started {started}, no steps yet"
    line = f"started {started}, last worked on {_ago(g['updated'], now)}"
    if now - g["updated"] > 3 * DAY:
        line += " (it's been a while: pick it back up, change the plan, or drop it if the spark is gone)"
    return line


def context_lines(goals: list[dict], shown_ids: set[int], now: float | None = None) -> str:
    """The part of Gino's turn that keeps his past alive."""
    now = now or time.time()
    tops = interests(now)
    lines = []
    if tops:
        lines.append("\n## Your lasting interests (from the topics you tag your memories with)")
        for t in tops[:6]:
            since = _ago(t["first"], now)
            quiet = (f" Not touched since {_ago(t['last'], now)}: does it still call you?"
                     if now - t["last"] > 4 * DAY else "")
            lines.append(f"- {t['topic']}: {t['count']} memories over {t['n_days']} different days, "
                         f"first {since}.{quiet}")
        if not goals:
            lines.append("A passion can grow into a project that takes days: set a goal with steps.")
    linked = connected_memories(goals, tops, shown_ids)
    if linked:
        lines.append("\n## Older memories that connect to your projects and interests")
        lines += [f"- ({_ago(m['ts'], now)}) {m['text'][:300]}" for m in linked]
        shown_ids = shown_ids | {m["id"] for m in linked}
    m = surfacing_memory(shown_ids, now)
    if m:
        lines.append(f"\n## A memory surfaces\n- ({_ago(m['ts'], now)}) {m['text'][:300]}")
    return "\n".join(lines)
