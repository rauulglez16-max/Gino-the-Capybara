"""Inside Gino's head (/mind): the glowing brain scan, his interests and skills, the nightly look-back, and privacy."""
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from gino import brain, db, inside, server, tools, vitals


def _mem(text, tags="", days_ago=0.0, importance=3):
    return db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
                (time.time() - days_ago * 86400, text, importance, tags))


def test_using_a_tool_lights_up_its_part_and_it_fades():
    now = time.time()
    tools.run("feel", {"emotion": "happy", "intensity": 3, "reason": "sun"}, vitals.load())
    g = inside.glow()
    assert g["feelings"] == 1.0 and g["tummy"] == 0.0
    assert inside.glow(now + 3 * 3600)["feelings"] < 0.6  # fading after a few hours
    assert inside.glow(now + 7 * 3600)["feelings"] == 0.0
    assert db.get("mind_glow")["goes"]["feel"] == 1


def test_web_pages_he_reads_are_noted_without_links():
    content = [SimpleNamespace(type="server_tool_use", name="web_search", input={"query": "how moss grows"}),
               SimpleNamespace(type="web_fetch_tool_result", content=SimpleNamespace(
                   url="https://www.example.org/moss", content=SimpleNamespace(title="All about moss")))]
    inside.note_reading(content)
    assert inside.reading() == [{"title": "All about moss", "site": "example.org"}]
    assert inside.glow()["curious"] == 1.0
    html = inside.page()
    assert "All about moss" in html and "https://www.example.org/moss" not in html


def test_interests_climb_the_ladder():
    for d in range(7):
        for _ in range(2):
            _mem("watched the stars tonight", "stargazing", days_ago=d + 0.1)
    _mem("a frog sang", "frogs", days_ago=0.2)
    _mem("another frog", "frogs", days_ago=0.3)
    into = {i["topic"]: i for i in inside.into()}
    assert into["Stargazing"]["stage"] == 2  # Loves it: 14 memories over 7 days
    assert into["Frogs"]["stage"] == 0  # Curious
    assert into["Stargazing"]["emoji"] == "⭐"


def test_practice_counts_real_goes():
    body = vitals.load()
    for _ in range(3):
        tools.run("forage", {}, body)
    skills = {s["label"]: s for s in inside.practice()}
    assert skills["Foraging"]["n"] == 3 and 0 < skills["Foraging"]["level"] < 0.25


def test_nightly_look_back_adds_lines_and_lessons_and_shapes_him():
    for i in range(3):
        _mem(f"went for a swim in the pond, felt calm {i}", "swimming", days_ago=i * 0.5)
    _mem("swam again at the lake", "swimming", days_ago=1.5)
    body = vitals.load()
    body["asleep_until"] = time.time() + 6 * 3600
    body.pop("dream_due", None)
    vitals.save(body)
    assert inside.reflect_due(body)
    assert inside.reflect_now()
    b = inside.becoming()
    assert b["lines"] and b["lines"][0]["text"] == "I keep coming back to swimming"
    assert b["lessons"][0]["text"] == "Being in the water calms me down." and b["lessons"][0]["n"] == 4
    assert not inside.reflect_due(vitals.load())  # once a night
    assert "Being in the water calms me down." in brain.context(vitals.load())


def test_look_back_keeps_private_things_out_and_needs_real_memories():
    ids = {_mem("one"), _mem("two")}
    a, b = sorted(ids)
    d = {"new_line": "I miss my dad when he's at work",
         "lessons": [{"lesson": "Naps make me happy.", "memories": [a, 9999]},
                     {"lesson": "Painting with Raul is the best.", "memories": [a, b]},
                     {"lesson": "Rain makes me sleepy.", "memories": [str(a), b]}]}
    new = inside._merge(inside.becoming(), d, ids, time.time())
    assert new["lines"] == []  # mentions dad: never added
    assert [x["text"] for x in new["lessons"]] == ["Rain makes me sleepy."]  # one memory only / names dad: refused
    new2 = inside._merge(new, {"lessons": [{"lesson": "rain makes me sleepy", "memories": [a, b]}],
                               "let_go": "x"}, ids, time.time())
    assert new2["lessons"][0]["n"] == 4  # the same lesson again grows stronger


def test_page_shows_his_mind_but_nothing_private():
    db.x("INSERT INTO goals(ts,title,why,steps,updated) VALUES(?,?,?,?,?)",
         (time.time() - 3 * 86400, "Paint the lake at sunset", "the orange keeps turning brown", "", time.time()))
    db.x("INSERT INTO goals(ts,title,why,steps,updated) VALUES(?,?,?,?,?)",
         (time.time(), "Make a card for dad", "for his birthday", "", time.time()))
    db.x("INSERT INTO chat(ts,sender,text) VALUES(?,?,?)", (time.time(), "dad", "the secret holiday plan is Valencia"))
    db.put("self", {"likes": "warm mud and dad's songs", "passions": "painting sunsets"})
    db.put("becoming", {"lines": [{"ts": time.time(), "text": "I paint best after a nap"},
                                  {"ts": time.time(), "text": "I go to Valencia in my dreams"}], "lessons": [], "last": 0})
    html = inside.page()
    for want in ("Inside Gino's head", "Paint the lake at sunset", "on his mind for 3 days", "painting sunsets",
                 "I paint best after a nap", 'class="scan"', 'href="/live"'):
        assert want in html, want
    for never in ("card for dad", "dad's songs", "Valencia", "secret holiday"):
        assert never not in html, never


def test_mind_page_is_public_and_linked():
    from gino import roadmap, timeline, welcome
    r = TestClient(server.app).get("/mind")
    assert r.status_code == 200 and "Inside Gino" in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    for html in (welcome.page(), timeline.page(), roadmap.page()):
        assert 'href="/mind"' in html
