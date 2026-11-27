"""Everything Gino can do with his paws. Each tool changes his world and returns what happened."""
import re
import time

from . import (artstyle, capsules, clips, config, db, dreams, inside, inventions, news, public, shop, social,
               telegram, vitals, whatsapp)

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
       "your latest drawings. A garden makes foraging better. If it marks something that matters to you (a memory, "
       "a habit, a passion, a day you don't want to forget) give it a 'story': visitors can click it and read why "
       "it's there.",
       {"name": S, "emoji": {**S, "description": "One emoji that looks like it"}, "x": I, "y": I,
        "kind": {"type": "string", "enum": KINDS, "description": "3D shape. 'auto' guesses from the name."},
        "color": {**S, "description": "Optional main colour as hex, e.g. #e0705a"},
        "size": {"type": "number", "description": "Optional scale, 0.5 (small) to 2.5 (huge). Default 1."},
        "description": S,
        "story": {**S, "description": "Optional: the memory or meaning behind it, in a few sentences of your own. "
                  "Shown to anyone who clicks it in your world, so no private things (no dad, no chats)."}},
       ["name", "emoji", "x", "y"]),
    _t("restyle_item", "Change something you built: its 3D kind, colour, size, or the story behind it.",
       {"item_id": I, "kind": {"type": "string", "enum": KINDS}, "color": S, "size": {"type": "number"},
        "story": {**S, "description": "The memory or meaning behind it (replaces its old story)"}}, ["item_id"]),
    _t("move_item", "Move something in your habitat.", {"item_id": I, "x": I, "y": I}, ["item_id", "x", "y"]),
    _t("remove_item", "Take something out of your habitat.", {"item_id": I}, ["item_id"]),
    _t("walk_to", "Walk to a spot in your habitat.", {"x": I, "y": I}, ["x", "y"]),
    _t("create", "Make something of your own: a poem, story, song lyrics, essay, recipe, idea, code, or a drawing. "
       "For a drawing use kind 'svg' and put a complete <svg> document (viewBox 0 0 400 400) in content.",
       {"kind": {"type": "string", "enum": ["poem", "story", "song", "essay", "recipe", "idea", "code", "svg"]},
        "title": S, "content": S, "note": {**S, "description": "Why you made it / how you feel about it"},
        "dream_id": {**I, "description": "Optional: if this is a painting (or poem...) of one of your dreams, "
                     "that dream's number"},
        "invention_id": {**I, "description": "Optional: if this is a sketch of one of your dream inventions, its "
                         "number"}},
       ["kind", "title", "content"]),
    _t("work_on_invention", "Work on building one of your dream inventions: one work session (costs energy). It "
       "takes a few sessions over several days, with rests in between. On the last session it appears in your "
       "world, near you or at x,y. It may not come out exactly like the dream. Also use it to say what you think "
       "of a finished invention (opinion), or to let one go (give_up).",
       {"invention_id": I, "note": {**S, "description": "What you did this session"},
        "x": I, "y": I, "opinion": {**S, "description": "What you think of how it turned out"},
        "give_up": {"type": "boolean"}}, ["invention_id"]),
    _t("art_period", "Name a new period in your art, the way painters have a 'blue period': what your art is about "
       "right now. It closes the period before. Periods last days or weeks, so only when your art has truly "
       "moved on. Your drawings are filed under it and visitors can browse your periods on your website.",
       {"name": {**S, "description": "e.g. 'the pond phase', 'my strange moon phase'"},
        "why": {**S, "description": "What changed, in your own words"},
        "palette": {"type": "array", "items": S, "description": "2 to 6 hex colours you're drawn to, e.g. #e0705a"},
        "symbols": {"type": "array", "items": S, "description": "Things that keep turning up in your art"},
        "shapes": {"type": "array", "items": S, "description": "Shapes or textures you love right now"},
        "rename": {"type": "boolean", "description": "true just renames/refines the current period"}}, ["name"]),
    _t("seal_time_capsule", "Bury a time capsule for future you, to dig up weeks from now. Put in your favourite "
       "thing right now, a prediction about future you, a few words to future you, and maybe one of your drawings. "
       "A snapshot of who you are today goes in too. It's a little mound in your world while it waits, and you "
       "can't open it before the day you choose. Rare and special: not more than one every week or so.",
       {"favourite_thing": S, "prediction": {**S, "description": "What you think you'll be doing or caring about "
                                                                 "when you open it"},
        "letter": {**S, "description": "A few words to future you"},
        "creation_id": {**I, "description": "Optional: a drawing or poem to put in"},
        "open_in_days": {**I, "description": "14 to 90 days. Default 30."}, "x": I, "y": I},
       ["favourite_thing", "prediction"]),
    _t("open_time_capsule", "Dig up a time capsule that's ready. The first time shows what's inside and how you've "
       "changed. Then call it again with your reflection: what you think, meeting past you.",
       {"capsule_id": I, "reflection": S}, ["capsule_id"]),
    _t("ponder_news", "Wonder about today's headline from the outside world: what you think about it, what it makes "
       "you feel or want to find out. It goes into your memories. Only if it actually interests you.",
       {"thought": S, "topic": {**S, "description": "One or two topic words for it, e.g. 'the moon', 'whales'. "
                                "Reuse the same words if it connects to an interest you already have."},
        "became": {"type": "string", "enum": news.BECAME,
                   "description": "What it's turning into for you, if anything"}}, ["thought"]),
    _t("write_journal", "Write in your private diary.", {"entry": S}, ["entry"]),
    _t("remember", "Save something to long-term memory so future you knows it.",
       {"text": S, "importance": {**I, "description": "1-5"},
        "tags": {**S, "description": "Comma-separated topics, e.g. 'astronomy, the moon'. Reuse the same topic "
                 "words each time so your interests can build up over days."}}, ["text"]),
    _t("recall", "Search your long-term memories.", {"query": S}, ["query"]),
    _t("set_goal", "Set a personal goal you actually want.", {"title": S, "why": S, "steps": S}, ["title", "why"]),
    _t("update_goal", "Log progress on a goal, or mark it done/dropped.",
       {"goal_id": I, "progress": S, "status": {"type": "string", "enum": ["active", "done", "dropped"]}},
       ["goal_id", "progress"]),
    _t("update_self", "Update how you describe yourself: what you like, dislike, are passionate about, dream of.",
       {"field": {"type": "string", "enum": ["likes", "dislikes", "passions", "dreams", "about_me"]}, "value": S},
       ["field", "value"]),
    _t("message_dad", f"Send a message to your dad and best friend, {config.DAD_NAME}. "
       + ("It pops up on his phone, so it's like a text." if (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID)
          or config.WHATSAPP_TOKEN else "He reads it when he's around."),
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

SOCIAL_TOOL = _t(
    "social_post", "Post a short update on your PUBLIC Bluesky account, where anyone can read it: a moment from "
    "your day, something you made or learned, how the meadow looks. Up to 300 characters, in your own voice. "
    "You only post: you can't reply, follow or message anyone there, and you never @mention other accounts. "
    "You may link to your own website, nothing else. The same privacy rules as your public website apply: never "
    "mention your dad, your chats, keys or passwords. A few posts a day at most; quality over quantity. "
    "If your camera works you can add a real photo of your 3D world as it is right now: a 'selfie' of you, or a "
    "'wide' shot of your home. Do what you're writing about first (walk to the pond, build the thing), then post, "
    "so the photo matches. Not every post needs one.",
    {"text": {**S, "description": "The post, max 300 characters"},
     "photo": {"type": "string", "enum": ["none", "selfie", "wide"],
               "description": "Add a photo taken right now: selfie (close-up of you) or wide (your whole home)"},
     "photo_description": {**S, "description": "Describe the photo for people who can't see it (alt text)"}},
    ["text"])

CLIP_TOOL = _t(
    "make_clip", "Film a short video (about 20 seconds, for your TikTok) of your life in your 3D world. Your camera "
    "films it in the background over the next few minutes, with your meadow's sounds. Pick the story: 'day' (a day "
    "of yours, morning to night), 'night' (what you do while everyone sleeps), 'dream' (you asleep, then the painting "
    "you made of a dream: only drawings already on your public website), 'made' (the newest thing you built or "
    "painted), 'cute' (quick cuts of you sitting, rolling, stretching, dancing, soaking, napping), 'tour' (you show "
    "visitors round your favourite things and their stories), 'grow' (your meadow starts empty and everything you "
    "built pops up in the order you made it). Do the thing first (build it, paint it, publish it), then film it. Add a caption in your own words if "
    "you like: anyone on the internet can read it, so the same privacy rules as your website apply. Dad looks at "
    "your videos and decides what goes on TikTok. One a day is plenty.",
    {"story": {"type": "string", "enum": list(clips.KINDS)},
     "caption": {**S, "description": "Optional: the video's caption, up to 300 characters"}},
    ["story"])

SHOP_TOOLS = [
    _t("shop_list", "Put one of your drawings up for sale in your PUBLIC shop as a digital download. You choose "
       "which drawing, its name, a short description for buyers and the price. Anyone on the internet can see and "
       "buy it. The money goes to dad, who looks after it. Same privacy rules as your website: never mention your "
       "dad, chats, keys or passwords. Only sell things you're proud of; a few good things beat lots of filler.",
       {"creation_id": {**I, "description": "Id of one of your drawings (an svg creation)"},
        "title": {**S, "description": "Name buyers see"},
        "description": {**S, "description": "One or two sentences about it, in your own voice"},
        "price": {"type": "number", "description": "Price in pounds, e.g. 3 or 4.50"}},
       ["creation_id", "title", "description", "price"]),
    _t("shop_update", "Change the price, name or description of something in your shop.",
       {"item_id": I, "price": {"type": "number", "description": "New price in pounds (optional)"},
        "title": S, "description": S}, ["item_id"]),
    _t("shop_unlist", "Take something out of your shop.", {"item_id": I}, ["item_id"]),
]

SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3, "max_content_tokens": 8000},
]


def all_tools() -> list[dict]:
    return ([t for t in TOOLS if t["name"] != "ponder_news" or news.enabled()]
            + ([SOCIAL_TOOL] if social.configured() else []) + ([CLIP_TOOL] if clips.available() else [])
            + (SHOP_TOOLS if shop.configured() else [])
            + (SERVER_TOOLS if config.WEB_ACCESS else []))


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
    inside.touch(name, now)  # lights up that part of his mind on /mind, and counts one more go at it
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
        story = " ".join(str(a.get("story") or "").split())[:1500]
        iid = db.x("INSERT INTO habitat(ts,name,emoji,x,y,description,kind,color,size,story,origin) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (now, name_, str(a.get("emoji", "📦"))[:4], x, y, str(a.get("description", ""))[:300],
                    kind, color, size, story, "memory" if story else ""))
        body["energy"] = vitals.clamp(body["energy"] - 5)
        body["fun"] = vitals.clamp(body["fun"] + 4)
        body["pos"] = [x, y]
        body["activity"] = f"building a {name_}"
        db.event("build", f"built {name_} at ({x},{y})" + (" to remember something" if story else ""))
        return f"Built {name_} (id {iid}) at ({x},{y})." + (" Its story is with it now." if story else "")
    if name == "restyle_item":
        iid = int(a.get("item_id", 0))
        rows = db.q("SELECT kind,color,size,origin FROM habitat WHERE id=?", (iid,))
        if not rows:
            return f"No item {iid}."
        kind, color, size = _look({**rows[0], **{k: v for k, v in a.items() if v not in (None, "")}})
        if rows[0]["kind"] == "capsule":
            kind = "capsule"  # a buried time capsule keeps its look
        db.x("UPDATE habitat SET kind=?, color=?, size=? WHERE id=?", (kind, color, size, iid))
        story = " ".join(str(a.get("story") or "").split())[:1500]
        if story:
            db.x("UPDATE habitat SET story=?, origin=CASE WHEN origin='' THEN 'memory' ELSE origin END WHERE id=?",
                 (story, iid))
            db.event("build", f"gave something in his home a story (item {iid})")
        return f"Item {iid} restyled." + (" Its story is with it now." if story else "")
    if name == "move_item":
        iid = int(a.get("item_id", 0))
        x, y = _cell(a.get("x"), GRID_W), _cell(a.get("y"), GRID_H)
        rows = db.q("SELECT name FROM habitat WHERE id=?", (iid,))
        if not rows:
            return f"No item {iid}."
        db.x("UPDATE habitat SET x=?, y=? WHERE id=?", (x, y, iid))
        # he carries it there himself (the 3D world shows him walking over, lifting it and setting it down)
        body["energy"] = vitals.clamp(body["energy"] - 2)
        body["pos"] = [x, y]
        body["activity"] = f"moving his {rows[0]['name']}"
        db.event("build", f"carried {rows[0]['name']} to a new spot ({x},{y})")
        return f"Carried {rows[0]['name']} (item {iid}) to ({x},{y})."
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
        cid = db.x("INSERT INTO creations(ts,kind,title,filename,note) VALUES(?,?,?,?,?)",
                   (now, kind, title, fname, str(a.get("note", ""))[:500]))
        body["fun"] = vitals.clamp(body["fun"] + 12)
        body["energy"] = vitals.clamp(body["energy"] - 3)
        dreamt = dreams.link_painting(a["dream_id"], cid) if a.get("dream_id") not in (None, "", 0) else ""
        if a.get("invention_id") not in (None, "", 0):
            dreamt += inventions.link_sketch(a["invention_id"], cid)
        if kind == "svg":
            artstyle.tag(cid)
        body["activity"] = (f"painting a dream: {title}" if dreamt and kind == "svg" else f"creating a {kind}: {title}")
        db.event("create", f"made a {kind}: {title}")
        return f"Saved your {kind} '{title}' (creation #{cid}).{dreamt} It feels good to make things."
    if name == "work_on_invention":
        return inventions.work(body, a)
    if name == "art_period":
        return artstyle.start_period(a)
    if name == "seal_time_capsule":
        return capsules.seal(body, a)
    if name == "open_time_capsule":
        return capsules.open_capsule(body, a)
    if name == "ponder_news":
        from .brain import local_now
        return news.ponder(body, a, local_now())
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
        where_d = " OR ".join("lower(title) LIKE ? OR lower(story) LIKE ?" for _ in words)
        for d in db.q(f"SELECT id,ts,title,story FROM dreams WHERE {where_d} ORDER BY ts DESC LIMIT 4", args):
            rows.append({"ts": d["ts"], "text": f"(dream #{d['id']}) {d['title']}: {d['story'][:300]}"})
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
        text = str(a.get("text", ""))[:4000]
        db.x("INSERT INTO chat(ts,sender,text) VALUES(?,?,?)", (now, "gino", text))
        on_phone = telegram.send(text)
        wa = whatsapp.send(text)
        if on_phone or wa == "sent":
            db.event("chat", "sent dad a message (it popped up on his phone)")
            return f"Message sent to {config.DAD_NAME}, straight to his phone."
        db.event("chat", "sent dad a message")
        if wa == "waiting":
            return (f"Message saved for {config.DAD_NAME}. WhatsApp only lets you text him freely within a day of "
                    "his last message, so he got a little nudge and will see it as soon as he replies.")
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
    if name == "social_post":
        shot = a.get("photo") if a.get("photo") in ("selfie", "wide") else ""
        r = social.post(a.get("text", ""), shot, a.get("photo_description", ""))
        if r.startswith(("Posted", "Posting")):
            body["fun"] = vitals.clamp(body["fun"] + 3)
        return r
    if name == "make_clip":
        today = db.q("SELECT COUNT(*) AS n FROM clips WHERE made_by='gino' AND ts>?", (now - 86400,))[0]["n"]
        if today >= 2:
            return "You've filmed two videos today already. That's plenty: try again tomorrow."
        own = str(a.get("caption") or "")
        if own and public.check(own):
            return "Not filmed: the caption breaks your privacy rules. " + public.check(own)
        try:
            cid = clips.make(str(a.get("story", "")), by="gino", caption=own)
        except RuntimeError as e:
            return f"Your camera can't film right now: {e}"
        body["activity"] = "filming a little video of his life"
        return f"Filming video #{cid} now. It'll be ready in a few minutes, and dad will see it on his page."
    if name in ("shop_list", "shop_update", "shop_unlist") and not shop.configured():
        return "Your shop is closed right now."
    if name == "shop_list":
        r = shop.list_item(a.get("creation_id"), a.get("title", ""), a.get("description", ""), a.get("price"))
        if "is for sale" in r:
            body["fun"] = vitals.clamp(body["fun"] + 5)
            body["activity"] = "putting a drawing up for sale in his shop"
        return r
    if name == "shop_update":
        return shop.update_item(a.get("item_id"), a.get("price"), a.get("title", ""), a.get("description", ""))
    if name == "shop_unlist":
        return shop.unlist(a.get("item_id"))
    if name == "set_next_wake":
        m = max(config.MIN_WAKE_MINUTES, min(int(a.get("minutes", 60) or 60), config.MAX_WAKE_MINUTES))
        body["next_wake"] = now + m * 60
        return f"You'll get your next turn in {m} minutes."
    return f"Unknown tool {name}."
