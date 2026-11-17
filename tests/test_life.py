"""Gino's life leaves traces: keepsakes with stories, dream inventions, art periods and time capsules."""
import datetime as dt
import json
import random
import time

from gino import artstyle, brain, capsules, db, dreams, inventions, keepsakes, live, tools, vitals

DAY = 86400


def body():
    b = vitals.load()
    b.update(energy=90, fun=50, pos=[5, 5])
    return b


def live_item(name):
    live._cache["data"] = None
    return next(h for h in live.state()["habitat"] if h["name"] == name)


# ---------------------------------------------------------------- keepsakes

def test_a_keepsake_carries_its_story_to_the_live_page():
    tools.run("build", {"name": "sunset bench", "emoji": "🪑", "x": 3, "y": 2, "kind": "bench",
                        "story": "I sit here every evening to watch the sun melt into the lake."}, body())
    tools.run("build", {"name": "plain rock", "emoji": "🪨", "x": 4, "y": 2}, body())
    item = live_item("sunset bench")
    assert "sun melt into the lake" in item["story"]
    assert item["since"]
    assert "story" not in live_item("plain rock")
    assert "📖" in brain.context(body())


def test_a_private_story_never_reaches_visitors():
    tools.run("build", {"name": "visiting bench", "emoji": "🪑", "x": 3, "y": 3,
                        "story": "Dad always visits me here in the evening."}, body())
    assert live_item("visiting bench")["story"] == keepsakes.PRIVATE_STORY


def test_restyle_can_give_an_old_thing_a_story():
    b = body()
    tools.run("build", {"name": "old oak", "emoji": "🌳", "x": 1, "y": 1}, b)
    iid = db.q("SELECT id FROM habitat")[0]["id"]
    tools.run("restyle_item", {"item_id": iid, "story": "The first thing I ever planted."}, b)
    row = db.q("SELECT story,origin FROM habitat WHERE id=?", (iid,))[0]
    assert row["story"] == "The first thing I ever planted." and row["origin"] == "memory"


def test_meaningful_moments_are_noticed_once_then_rest():
    for d in (5, 3, 1):
        db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
             (time.time() - d * DAY, "Watched the moon rise", 3, "the moon"))
    assert any(k == "interest:the moon" for k, _ in keepsakes.candidates())
    first = keepsakes.context_lines(chance=1)
    assert "the moon" in first and "story" in first
    assert "the moon" not in keepsakes.context_lines(chance=1)  # not nagging every turn
    tools.run("build", {"name": "moon stone", "emoji": "🌕", "x": 2, "y": 2, "story": "For the moon."}, body())
    assert not any(k == "interest:the moon" for k, _ in keepsakes.candidates())  # already marked


def test_dads_evening_visits_become_a_pattern():
    tz = brain.tz()
    for d in (1, 2, 4, 6):
        t = (dt.datetime.now(tz) - dt.timedelta(days=d)).replace(hour=20, minute=0).timestamp()
        db.x("INSERT INTO chat(ts,sender,text) VALUES(?,?,?)", (t, "dad", "hi Gino"))
    assert keepsakes.visit_pattern() == {"part": "evening", "days": 4}


# ---------------------------------------------------------------- dream inventions

def _dream_with_invention():
    b = body()
    f = dreams.fragments(b)
    d = dreams.fake_dream(f, 3, invent=True)
    did = dreams.save(b, d, 3)
    return did, db.q("SELECT * FROM inventions WHERE dream_id=?", (did,))[0]


def test_a_dream_can_invent_something():
    assert inventions.INVENT_PROMPT in dreams.prompt(body(), 3, dreams.fragments(body()), invent=True)
    assert inventions.INVENT_PROMPT not in dreams.prompt(body(), 3, dreams.fragments(body()))
    did, inv = _dream_with_invention()
    assert inv["status"] == "dreamed"
    assert "invented something" in dreams.waking_lines(did)
    assert "dream inventions" in brain.context(body())


def test_building_an_invention_takes_several_sessions_with_rests(monkeypatch):
    _, inv = _dream_with_invention()
    db.x("UPDATE inventions SET needed=3 WHERE id=?", (inv["id"],))
    b = body()
    assert "Session 1" in tools.run("work_on_invention", {"invention_id": inv["id"], "note": "found sticks"}, b)
    assert "need a rest" in tools.run("work_on_invention", {"invention_id": inv["id"]}, b)
    for _ in range(2):  # pretend the rest happened
        db.x("UPDATE inventions SET last_session=last_session-? WHERE id=?", (5 * 3600, inv["id"]))
        b["energy"] = 90
        monkeypatch.setattr(inventions.random, "random", lambda: 0.0)  # force a twist on the last session
        monkeypatch.setattr(inventions.random, "choice", lambda xs: xs[0])
        out = tools.run("work_on_invention", {"invention_id": inv["id"], "x": 9, "y": 4}, b)
    assert "finished" in out and "didn't come out like the dream" in out
    done = db.q("SELECT * FROM inventions WHERE id=?", (inv["id"],))[0]
    item = db.q("SELECT * FROM habitat WHERE id=?", (done["item_id"],))[0]
    assert done["status"] == "built" and item["origin"] == f"invention:{inv['id']}" and item["size"] == 0.6
    tools.run("work_on_invention", {"invention_id": inv["id"], "opinion": "Small, but mine. I love it."}, b)
    assert "Small, but mine" in live_item(item["name"])["story"]
    tools.run("work_on_invention", {"invention_id": inv["id"], "opinion": "I'll show it to dad."}, b)
    story = live_item(item["name"])["story"]
    assert "dad" not in story.lower() and "dreamed this up" in story


def test_a_sketch_is_linked_to_its_invention():
    _, inv = _dream_with_invention()
    tools.run("create", {"kind": "svg", "title": "Lantern plan", "invention_id": inv["id"],
                         "content": '<svg viewBox="0 0 400 400"><circle r="9" fill="#f6c833"/></svg>'}, body())
    assert db.q("SELECT sketch_id FROM inventions WHERE id=?", (inv["id"],))[0]["sketch_id"]


# ---------------------------------------------------------------- art style

ORANGE = '<svg viewBox="0 0 400 400"><rect width="400" height="400" fill="#f08a2c"/><circle r="40" fill="hsl(30,90%,55%)"/></svg>'
BLUE = ('<svg viewBox="0 0 400 400"><defs><linearGradient id="g"><stop stop-color="#1f5fd0"/></linearGradient></defs>'
        '<path d="M0 0 C 50 50 100 0 200 40" fill="#3f7fd6"/><ellipse rx="9" ry="4" fill="navy"/></svg>')


def draw(title, svg, days_ago=0.0):
    tools.run("create", {"kind": "svg", "title": title, "content": svg}, body())
    cid = db.q("SELECT id FROM creations ORDER BY id DESC LIMIT 1")[0]["id"]
    db.x("UPDATE creations SET ts=? WHERE id=?", (time.time() - days_ago * DAY, cid))
    return cid


def test_reading_a_drawing():
    colours, shapes = artstyle.measure(BLUE)
    assert set(colours) == {"blue"} and "curves" in shapes and "gradients" in shapes
    assert artstyle.fingerprint([{"title": "x", "filename": "none"}])["n"] == 1


def test_periods_file_drawings_and_notice_drift():
    for i in range(3):
        draw(f"Orange sun {i}", ORANGE, days_ago=8)
    assert "haven't named your art period" in artstyle.context_lines()
    assert "new chapter" in tools.run("art_period", {"name": "the orange phase", "palette": ["#f08a2c", "nope"],
                                                     "symbols": ["the sun"]}, body())
    p = artstyle.current()
    assert json.loads(p["palette"]) == ["#f08a2c"]
    db.x("UPDATE art_periods SET started=? WHERE id=?", (time.time() - 9 * DAY, p["id"]))
    for i in range(4):
        draw(f"Orange sun again {i}", ORANGE, days_ago=7)
    for i in range(5):
        draw(f"Deep sea {i}", BLUE)
    assert db.q("SELECT COUNT(*) AS n FROM creations WHERE period_id=?", (p["id"],))[0]["n"] == 9
    text = artstyle.context_lines()
    assert "the orange phase" in text and "blue" in text and "new period starting" in text
    assert "only began" not in tools.run("art_period", {"name": "the deep blue phase"}, body())
    assert "only began" in tools.run("art_period", {"name": "another one"}, body())


def test_periods_page_only_shows_public_drawings():
    from fastapi.testclient import TestClient
    from gino.server import app
    hidden = draw("Secret sketch", ORANGE)
    shown = draw("Pond at noon", BLUE)
    db.x("UPDATE creations SET period_id=NULL")
    tools.run("art_period", {"name": "the pond phase", "why": "Water everywhere."}, body())
    db.x("UPDATE creations SET period_id=(SELECT id FROM art_periods)")
    db.x("INSERT INTO posts(ts,updated,kind,slug,title,body,creation_id) VALUES(?,?,?,?,?,?,?)",
         (time.time(), time.time(), "page", "pond", "Pond", "my pond", shown))
    html = TestClient(app).get("/blog/periods").text
    assert "the pond phase" in html and f"/blog/art/{shown}.svg" in html and f"/blog/art/{hidden}.svg" not in html


# ---------------------------------------------------------------- time capsules

def test_a_time_capsule_waits_then_opens():
    b = body()
    out = tools.run("seal_time_capsule", {"favourite_thing": "the warm pond", "prediction": "I'll have a boat",
                                          "letter": "Stay chill", "open_in_days": 3}, b)  # clamped to 14
    assert "14 days" in out
    cap = db.q("SELECT * FROM capsules")[0]
    item = db.q("SELECT * FROM habitat WHERE id=?", (cap["item_id"],))[0]
    assert item["kind"] == "capsule"
    assert "buried a time capsule" in live_item("time capsule")["story"]
    assert "boat" not in live_item("time capsule")["story"]  # sealed means sealed
    assert "few days ago" in tools.run("seal_time_capsule", {"favourite_thing": "x", "prediction": "y"}, b)
    assert "Not yet" in tools.run("open_time_capsule", {"capsule_id": cap["id"]}, b)
    assert "opens in 14 days" in capsules.context_lines(b)
    db.x("UPDATE capsules SET open_after=? WHERE id=?", (time.time() - 1, cap["id"]))
    assert "READY" in capsules.context_lines(b)
    opened = tools.run("open_time_capsule", {"capsule_id": cap["id"]}, b)
    assert "I'll have a boat" in opened and "Then and now" in opened
    tools.run("open_time_capsule", {"capsule_id": cap["id"], "reflection": "No boat. Mostly lamps. Happy anyway."}, b)
    story = live_item("opened time capsule")["story"]
    assert "Mostly lamps" in story and "I'll have a boat" in story


def test_private_words_in_a_capsule_stay_private():
    b = body()
    tools.run("seal_time_capsule", {"favourite_thing": "hugs from dad", "prediction": "More drawings"}, b)
    cid = db.q("SELECT id FROM capsules")[0]["id"]
    db.x("UPDATE capsules SET open_after=? WHERE id=?", (time.time() - 1, cid))
    tools.run("open_time_capsule", {"capsule_id": cid, "reflection": "I drew so much!"}, b)
    story = live_item("opened time capsule")["story"]
    assert "dad" not in story.lower() and "I drew so much" in story


# ---------------------------------------------------------------- the practice brain lives it all

def test_practice_brain_runs_with_all_of_it():
    random.seed(4)
    b = body()
    b["born"] = time.time() - 5 * DAY
    _dream_with_invention()
    for _ in range(4):
        draw("Sun", ORANGE)
    for _ in range(6):
        b["energy"], b["fullness"] = 90, 90
        db.x("UPDATE inventions SET last_session=last_session-? WHERE last_session IS NOT NULL", (5 * 3600,))
        brain.fake_turn(b)
    assert artstyle.current()
    assert db.q("SELECT status FROM inventions")[0]["status"] in ("building", "built")
