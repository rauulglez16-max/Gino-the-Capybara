"""'Since your last visit...': what Gino got up to while dad was away, for the top of dad's private page.

Built straight from Gino's own records (no AI call, so it's free). A "visit" is dad having the private page
open; if he's been away for 30 minutes or more, the next visit starts with a recap of everything since.
"""
import json
import time

from . import continuity, db

GAP = 30 * 60  # away this long = a new visit
TOUCH_EVERY = 60  # don't write to the database on every single request


def seen(now: float | None = None) -> None:
    """Dad is looking at the private page right now."""
    now = now or time.time()
    last = db.get("dad_last_seen", 0) or 0
    if now - last >= GAP:  # a new visit: remember where the last one ended
        db.put("dad_visit_since", last or now)
    if now - last >= TOUCH_EVERY:
        db.put("dad_last_seen", now)


def _away(seconds: float) -> str:
    h = seconds / 3600
    if h < 1:
        return f"{int(seconds // 60)} minutes"
    if h < 36:
        return f"{h:.0f} hour{'s' if round(h) != 1 else ''}"
    return f"{h / 24:.0f} days"


def build(since: float, now: float | None = None) -> dict:
    """Everything worth telling dad about since `since`."""
    now = now or time.time()
    a = (since,)
    made = db.q("SELECT id,ts,kind,title,filename,dream_id FROM creations WHERE ts>? ORDER BY ts DESC LIMIT 12", a)
    dreams = db.q("SELECT id,ts,title,strangeness,feeling FROM dreams WHERE ts>? ORDER BY ts DESC LIMIT 6", a)
    new_goals = db.q("SELECT id,title,why FROM goals WHERE ts>? ORDER BY ts", a)
    done = db.q("SELECT id,title FROM goals WHERE status='done' AND updated>? ORDER BY updated", a)
    worked = []
    for g in db.q("SELECT id,title,progress FROM goals WHERE status='active' AND updated>? AND ts<=? "
                  "ORDER BY updated DESC LIMIT 6", (since, since)):
        steps = [ln for ln in (g["progress"] or "").splitlines() if ln.strip()]
        worked.append({"id": g["id"], "title": g["title"], "latest": steps[-1][:240] if steps else ""})
    built = [r["text"] for r in db.q("SELECT text FROM events WHERE kind='build' AND ts>? ORDER BY ts LIMIT 10", a)]
    learned = [r["text"][:240] for r in db.q("SELECT text FROM memories WHERE ts>? AND importance>=3 "
                                             "ORDER BY importance DESC, ts DESC LIMIT 6", a)]
    published = db.q("SELECT kind,slug,title FROM posts WHERE updated>? ORDER BY updated DESC LIMIT 6", a)
    messages = db.q("SELECT COUNT(*) AS n FROM chat WHERE sender='gino' AND ts>?", a)[0]["n"]
    journal = db.q("SELECT ts,text,emotion FROM journal WHERE ts>? ORDER BY ts DESC LIMIT 1", a)
    feelings = [r["text"] for r in db.q("SELECT text FROM events WHERE kind='feel' AND ts>? ORDER BY ts", a)]
    sales = []
    try:
        sales = db.q("SELECT i.title, s.amount_pence FROM shop_sales s JOIN shop_items i ON i.id=s.item_id "
                     "WHERE s.ts>? ORDER BY s.ts", a)
    except Exception:  # shop never set up
        pass
    new_interests = [t["topic"] for t in continuity.interests(now) if t["first"] > since][:4]
    turns = db.q("SELECT COUNT(*) AS n FROM events WHERE kind='turn' AND ts>?", a)[0]["n"]
    out = {
        "since": since, "away": _away(now - since), "turns": turns,
        "made": made, "dreams": dreams, "new_goals": new_goals, "done_goals": done, "worked_on": worked,
        "built": built, "learned": learned, "published": published, "messages": messages,
        "journal": journal[0] if journal else None, "feelings": feelings[-3:], "sales": sales,
        "new_interests": new_interests,
    }
    out["empty"] = not any(out[k] for k in ("made", "dreams", "new_goals", "done_goals", "worked_on", "built",
                                            "learned", "published", "messages", "journal", "sales",
                                            "new_interests"))
    return out


def for_dad(now: float | None = None) -> dict:
    """The recap for this visit, or {'show': False} if dad was here a moment ago."""
    now = now or time.time()
    seen(now)
    since = db.get("dad_visit_since", 0) or 0
    if not since or now - since < GAP:
        return {"show": False}
    r = build(since, now)
    return {"show": not r["empty"], **json.loads(json.dumps(r, default=str))}
