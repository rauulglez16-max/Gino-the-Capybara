"""Everything Gino can do with his paws. Each tool changes his world and returns what happened."""
import re
import time

from . import config, db, vitals

GRID_W, GRID_H = 16, 10


def _t(name, desc, props, required=()):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": list(required)}}


S = {"type": "string"}
I = {"type": "integer"}

TOOLS = [
    _t("feel", "Say how you feel right now and why. Use whenever your feelings change.",
       {"emotion": S, "intensity": {**I, "description": "1 (barely) to 5 (overwhelming)"}, "reason": S},
       ["emotion", "intensity", "reason"]),
    _t("think", "Record your current inner thought (shown in your thought bubble).", {"thought": S}, ["thought"]),
    _t("forage", "Wander around looking for food. Costs some energy. A garden in your habitat finds better food.", {}),
    _t("eat", "Eat food from your pantry.", {"food": S, "amount": I}, ["food"]),
    _t("sleep", "Go to sleep. Your turn ends and you wake up after this many hours (0.25-10).",
       {"hours": {"type": "number"}}, ["hours"]),
    _t("build", "Build or place a thing in your habitat, a 16x10 grid (x 0-15, y 0-9). Costs energy. "
       "Things like a pond, garden, bed, hammock, bookshelf, art wall make your home cozier and can unlock new things.",
       {"name": S, "emoji": {**S, "description": "One emoji that looks like it"}, "x": I, "y": I,
        "description": S}, ["name", "emoji", "x", "y"]),
    _t("move_item", "Move something in your habitat.", {"item_id": I, "x": I, "y": I}, ["item_id", "x", "y"]),
    _t("remove_item", "Take something out of your habitat.", {"item_id": I}, ["item_id"]),
    _t("walk_to", "Walk to a spot in your habitat.", {"x": I, "y": I}, ["x", "y"]),
    _t("create", "Make something of your own: a poem, story, song lyrics, essay, recipe, idea, code, or a drawing. "
       "For a drawing use kind 'svg' and put a complete <svg> document (viewBox 0 0 400 400) in content.",
       {"kind": {"type": "string", "enum": ["poem", "story", "song", "essay", "recipe", "idea", "code", "svg"]},
        "title": S, "content": S, "note": {**S, "description": "Why you made it / how you feel about it"}},
       ["kind", "title", "content"]),
    _t("write_journal", "Write in your private diary.", {"entry": S}, ["entry"]),
    _t("remember", "Save something to long-term memory so future you knows it.",
       {"text": S, "importance": {**I, "description": "1-5"}, "tags": S}, ["text"]),
    _t("recall", "Search your long-term memories.", {"query": S}, ["query"]),
    _t("set_goal", "Set a personal goal you actually want.", {"title": S, "why": S, "steps": S}, ["title", "why"]),
    _t("update_goal", "Log progress on a goal, or mark it done/dropped.",
       {"goal_id": I, "progress": S, "status": {"type": "string", "enum": ["active", "done", "dropped"]}},
       ["goal_id", "progress"]),
    _t("update_self", "Update how you describe yourself: what you like, dislike, are passionate about, dream of.",
       {"field": {"type": "string", "enum": ["likes", "dislikes", "passions", "dreams", "about_me"]}, "value": S},
       ["field", "value"]),
    _t("message_dad", f"Send a message to your dad and best friend, {config.DAD_NAME}. He reads it when he's around.",
       {"text": S}, ["text"]),
    _t("set_next_wake", "Choose how many minutes until your next turn (you'll still wake if dad messages you).",
       {"minutes": I}, ["minutes"]),
]

SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3, "max_content_tokens": 8000},
]


def all_tools() -> list[dict]:
    return TOOLS + (SERVER_TOOLS if config.WEB_ACCESS else [])


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "untitled"


def _cell(v, hi) -> int:
    try:
        return max(0, min(int(v), hi - 1))
    except (TypeError, ValueError):
        return 0


class TurnEnded(Exception):
    pass


def run(name: str, a: dict, body: dict) -> str:
    """Execute one tool against Gino's body/world. Returns text for the model."""
    now = time.time()
    if name == "feel":
        body["emotion"] = str(a.get("emotion", "")).lower()[:30]
        body["emotion_intensity"] = _cell(a.get("intensity", 3), 6) or 1
        body["emotion_reason"] = str(a.get("reason", ""))[:300]
        db.event("feel", f"feels {body['emotion']} ({body['emotion_intensity']}/5): {body['emotion_reason']}")
        return "Noted."
    if name == "think":
        body["thought"] = str(a.get("thought", ""))[:400]
        return "Noted."
    if name == "forage":
        r = vitals.forage(body)
        db.event("food", r)
        return r
    if name == "eat":
        r = vitals.eat(body, str(a.get("food", "")), int(a.get("amount", 1) or 1))
        db.event("food", r)
        return r
    if name == "sleep":
        r = vitals.sleep(body, float(a.get("hours", 1)))
        db.event("sleep", r)
        raise TurnEnded(r)
    if name == "build":
        if body["energy"] < 5:
            return "Too tired to build. Rest first."
        x, y = _cell(a.get("x"), GRID_W), _cell(a.get("y"), GRID_H)
        if db.q("SELECT 1 FROM habitat WHERE x=? AND y=?", (x, y)):
            free = [(cx, cy) for cy in range(GRID_H) for cx in range(GRID_W)
                    if not db.q("SELECT 1 FROM habitat WHERE x=? AND y=?", (cx, cy))][:6]
            return f"Something is already at ({x},{y}). Some free spots: {free}"
        name_ = str(a.get("name", "thing"))[:40]
        iid = db.x("INSERT INTO habitat(ts,name,emoji,x,y,description) VALUES(?,?,?,?,?,?)",
                   (now, name_, str(a.get("emoji", "📦"))[:4], x, y, str(a.get("description", ""))[:300]))
        body["energy"] = vitals.clamp(body["energy"] - 5)
        body["fun"] = vitals.clamp(body["fun"] + 4)
        body["pos"] = [x, y]
        body["activity"] = f"building a {name_}"
        db.event("build", f"built {name_} at ({x},{y})")
        return f"Built {name_} (id {iid}) at ({x},{y})."
    if name == "move_item":
        iid = int(a.get("item_id", 0))
        x, y = _cell(a.get("x"), GRID_W), _cell(a.get("y"), GRID_H)
        if not db.q("SELECT 1 FROM habitat WHERE id=?", (iid,)):
            return f"No item {iid}."
        db.x("UPDATE habitat SET x=?, y=? WHERE id=?", (x, y, iid))
        return f"Moved item {iid} to ({x},{y})."
    if name == "remove_item":
        rows = db.q("SELECT name FROM habitat WHERE id=?", (int(a.get("item_id", 0)),))
        if not rows:
            return "No such item."
        db.x("DELETE FROM habitat WHERE id=?", (int(a["item_id"]),))
        db.event("build", f"removed {rows[0]['name']}")
        return f"Removed {rows[0]['name']}."
    if name == "walk_to":
        body["pos"] = [_cell(a.get("x"), GRID_W), _cell(a.get("y"), GRID_H)]
        return f"Walked to {body['pos']}."
    if name == "create":
        kind = str(a.get("kind", "idea"))
        title = str(a.get("title", "Untitled"))[:80]
        content = str(a.get("content", ""))
        if kind == "svg":
            m = re.search(r"<svg[\s\S]*</svg>", content)
            if not m:
                return "That drawing wasn't a complete <svg>...</svg> document. Try again."
            content = re.sub(r"<script[\s\S]*?</script>", "", m.group(0), flags=re.I)
            ext = "svg"
        else:
            ext = {"code": "txt"}.get(kind, "md")
        fname = f"{int(now)}-{_slug(title)}.{ext}"
        (config.DATA_DIR / "creations" / fname).write_text(content, encoding="utf-8")
        db.x("INSERT INTO creations(ts,kind,title,filename,note) VALUES(?,?,?,?,?)",
             (now, kind, title, fname, str(a.get("note", ""))[:500]))
        body["fun"] = vitals.clamp(body["fun"] + 12)
        body["energy"] = vitals.clamp(body["energy"] - 3)
        body["activity"] = f"creating a {kind}: {title}"
        db.event("create", f"made a {kind}: {title}")
        return f"Saved your {kind} '{title}'. It feels good to make things."
    if name == "write_journal":
        db.x("INSERT INTO journal(ts,text,emotion) VALUES(?,?,?)",
             (now, str(a.get("entry", ""))[:5000], body.get("emotion")))
        return "Written in your diary."
    if name == "remember":
        imp = min(5, max(1, int(a.get("importance", 2) or 2)))
        db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
             (now, str(a.get("text", ""))[:1000], imp, str(a.get("tags", ""))[:100]))
        return "Remembered."
    if name == "recall":
        words = [w for w in re.findall(r"\w+", str(a.get("query", "")).lower()) if len(w) > 2][:5]
        if not words:
            return "Nothing to search for."
        where = " OR ".join("lower(text) LIKE ? OR lower(tags) LIKE ?" for _ in words)
        args = tuple(v for w in words for v in (f"%{w}%", f"%{w}%"))
        rows = db.q(f"SELECT id,ts,text,importance FROM memories WHERE {where} "
                    "ORDER BY importance DESC, ts DESC LIMIT 12", args)
        if not rows:
            return "No memories about that."
        return "\n".join(f"- [{time.strftime('%Y-%m-%d', time.localtime(r['ts']))}] {r['text']}" for r in rows)
    if name == "set_goal":
        gid = db.x("INSERT INTO goals(ts,title,why,steps,updated) VALUES(?,?,?,?,?)",
                   (now, str(a.get("title", ""))[:200], str(a.get("why", ""))[:500],
                    str(a.get("steps", ""))[:1000], now))
        db.event("goal", f"new goal: {a.get('title')}")
        return f"Goal #{gid} set."
    if name == "update_goal":
        gid = int(a.get("goal_id", 0))
        g = db.q("SELECT progress,title FROM goals WHERE id=?", (gid,))
        if not g:
            return f"No goal #{gid}."
        stamp = time.strftime("%b %d", time.localtime(now))
        progress = (g[0]["progress"] + f"\n[{stamp}] {a.get('progress', '')}").strip()[-3000:]
        status = a.get("status") if a.get("status") in ("active", "done", "dropped") else "active"
        db.x("UPDATE goals SET progress=?, status=?, updated=? WHERE id=?", (progress, status, now, gid))
        if status == "done":
            body["fun"] = vitals.clamp(body["fun"] + 15)
            db.event("goal", f"achieved goal: {g[0]['title']}")
        return f"Goal #{gid} updated ({status})."
    if name == "update_self":
        me = db.get("self", {})
        me[str(a.get("field", "about_me"))] = str(a.get("value", ""))[:1000]
        db.put("self", me)
        return "Updated who you are."
    if name == "message_dad":
        db.x("INSERT INTO chat(ts,sender,text) VALUES(?,?,?)", (now, "gino", str(a.get("text", ""))[:4000]))
        db.event("chat", "sent dad a message")
        return f"Message sent to {config.DAD_NAME}."
    if name == "set_next_wake":
        m = max(config.MIN_WAKE_MINUTES, min(int(a.get("minutes", 60) or 60), config.MAX_WAKE_MINUTES))
        body["next_wake"] = now + m * 60
        return f"You'll get your next turn in {m} minutes."
    return f"Unknown tool {name}."
