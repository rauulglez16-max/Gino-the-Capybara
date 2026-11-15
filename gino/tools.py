"""Everything Gino can do with his paws. Each tool changes his world and returns what happened."""
import re
import time

from . import config, db, public, vitals

GRID_W, GRID_H = 16, 10


def _t(name, desc, props, required=()):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": list(required)}}


S = {"type": "string"}
I = {"type": "integer"}

KINDS = ["auto", "tree", "fruit_tree", "pine", "bush", "flowers", "mushroom", "rock", "pond", "fountain", "well",
         "garden", "pumpkins", "beehive", "bed", "hammock", "swing", "bench", "table", "picnic", "bookshelf", "easel",
         "gallery", "statue", "sign", "mailbox", "flag", "fence", "path", "bridge", "arch", "lamp", "campfire", "house",
         "tent", "windmill", "boat", "snowman", "telescope", "piano"]


def _look(a: dict) -> tuple[str, str, float]:
    kind = a.get("kind") if a.get("kind") in KINDS and a.get("kind") != "auto" else ""
    color = str(a.get("color") or "")
    color = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else ""
    try:
        size = max(0.5, min(float(a.get("size") or 1), 2.5))
    except (TypeError, ValueError):
        size = 1.0
    return kind, color, size


TOOLS = [
    _t("feel", "Say how you feel right now and why. Use whenever your feelings change.",
       {"emotion": S, "intensity": {**I, "description": "1 (barely) to 5 (overwhelming)"}, "reason": S},
       ["emotion", "intensity", "reason"]),
    _t("think", "Record your current inner thought (shown in your thought bubble).", {"thought": S}, ["thought"]),
    _t("forage", "Wander around looking for food. Costs some energy. A garden in your habitat finds better food.", {}),
    _t("eat", "Eat food from your pantry.", {"food": S, "amount": I}, ["food"]),
    _t("sleep", "Go to sleep. Your turn ends and you wake up after this many hours (0.25-10).",
       {"hours": {"type": "number"}}, ["hours"]),
    _t("build", "Build or place a thing in your 3D world. Your home is a 16x10 meadow (x 0-15, y 0-9) surrounded by "
       "hills and forest, and dad can fly around it and see everything you make. Costs energy. Pick a 'kind' to "
       "choose its 3D shape; anything else you invent appears as its emoji on a little plinth. You can swim in a "
       "pond by walking onto it. Lamps, campfires and house windows glow at night. An easel or gallery shows "
       "your latest drawings. A garden makes foraging better.",
       {"name": S, "emoji": {**S, "description": "One emoji that looks like it"}, "x": I, "y": I,
        "kind": {"type": "string", "enum": KINDS, "description": "3D shape. 'auto' guesses from the name."},
        "color": {**S, "description": "Optional main colour as hex, e.g. #e0705a"},
        "size": {"type": "number", "description": "Optional scale, 0.5 (small) to 2.5 (huge). Default 1."},
        "description": S}, ["name", "emoji", "x", "y"]),
    _t("restyle_item", "Change the look of something you built: its 3D kind, colour or size.",
       {"item_id": I, "kind": {"type": "string", "enum": KINDS}, "color": S, "size": {"type": "number"}}, ["item_id"]),
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
    _t("public_diary", "Write in your PUBLIC diary on your own website, which anyone on the internet can read. "
       "Tell the world about your day: what you did, what you learned, what you made, how it felt. One diary page "
       "per day; writing again the same day adds to it (or set replace to rewrite it). Unlike write_journal, this "
       "is public, so NEVER mention your dad (not his name, not that you have one), your chats with him, keys, "
       "passwords or anything private. It's rejected if it does. Markdown works (## headings, **bold**, - lists, "
       "[links](https://...)).",
       {"entry": S, "title": {**S, "description": "Optional title for today's page"},
        "replace": {"type": "boolean", "description": "true rewrites today's entry instead of adding to it"}},
       ["entry"]),
    _t("public_page", "Publish (or update) a page on your public website: a project, a guide to something you "
       "learned, a list of favourite things, a showcase of one of your creations. Anyone can read it, so the same "
       "privacy rules as public_diary apply. Use the same slug again to update a page. To show off a poem, story "
       "or drawing you made, pass its creation_id and write a few words about it in content.",
       {"title": S, "content": {**S, "description": "The page, in markdown"},
        "slug": {**S, "description": "Short web address name, e.g. 'my-pond'. Defaults to the title."},
        "summary": {**S, "description": "One line shown on your homepage"},
        "creation_id": {**I, "description": "Optional: id of one of your creations to show on the page"}},
       ["title", "content"]),
    _t("public_unpublish", "Take a diary day or page off your public website.",
       {"kind": {"type": "string", "enum": ["diary", "page"]},
        "slug": {**S, "description": "The page's slug, or the diary's date like 2026-11-15"}}, ["kind", "slug"]),
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
        kind, color, size = _look(a)
        iid = db.x("INSERT INTO habitat(ts,name,emoji,x,y,description,kind,color,size) VALUES(?,?,?,?,?,?,?,?,?)",
                   (now, name_, str(a.get("emoji", "📦"))[:4], x, y, str(a.get("description", ""))[:300],
                    kind, color, size))
        body["energy"] = vitals.clamp(body["energy"] - 5)
        body["fun"] = vitals.clamp(body["fun"] + 4)
        body["pos"] = [x, y]
        body["activity"] = f"building a {name_}"
        db.event("build", f"built {name_} at ({x},{y})")
        return f"Built {name_} (id {iid}) at ({x},{y})."
    if name == "restyle_item":
        iid = int(a.get("item_id", 0))
        rows = db.q("SELECT kind,color,size FROM habitat WHERE id=?", (iid,))
        if not rows:
            return f"No item {iid}."
        kind, color, size = _look({**rows[0], **{k: v for k, v in a.items() if v not in (None, "")}})
        db.x("UPDATE habitat SET kind=?, color=?, size=? WHERE id=?", (kind, color, size, iid))
        return f"Item {iid} restyled."
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
    if name == "public_diary":
        return public.write_diary(a.get("entry", ""), a.get("title", ""), bool(a.get("replace")))
    if name == "public_page":
        cid = a.get("creation_id")
        try:
            cid = int(cid) if cid not in (None, "", 0) else None
        except (TypeError, ValueError):
            cid = None
        r = public.write_page(a.get("title", ""), a.get("content", ""), a.get("slug", ""), a.get("summary", ""), cid)
        if r.startswith(("Published", "Updated")):
            body["fun"] = vitals.clamp(body["fun"] + 6)
        return r
    if name == "public_unpublish":
        return public.unpublish(str(a.get("kind", "page")), str(a.get("slug", "")))
    if name == "set_next_wake":
        m = max(config.MIN_WAKE_MINUTES, min(int(a.get("minutes", 60) or 60), config.MAX_WAKE_MINUTES))
        body["next_wake"] = now + m * 60
        return f"You'll get your next turn in {m} minutes."
    return f"Unknown tool {name}."
