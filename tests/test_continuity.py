"""Gino's days should add up: interests build over days, old memories come back, dad gets a recap."""
import time

from gino import brain, continuity, db, recap, vitals

DAY = 86400


def remember(text, tags="", days_ago=0.0, importance=3):
    return db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
                (time.time() - days_ago * DAY, text, importance, tags))


def test_a_topic_over_several_days_becomes_a_lasting_interest():
    remember("Saw the moon through the clouds", "astronomy, the moon", 6)
    remember("Read about craters", "Astronomy", 4)
    remember("Counted stars", "astronomy; stars", 1)
    remember("Ate a carrot", "food", 0)
    tops = continuity.interests()
    assert tops[0]["topic"] == "astronomy"
    assert tops[0]["n_days"] == 3
    assert "food" not in [t["topic"] for t in tops]  # once isn't an interest yet


def test_old_memories_that_match_a_project_come_back():
    old = remember("The moon has a crater called Tycho that shines like a star", "", 20, importance=2)
    for i in range(30):  # lots of newer, unrelated memories push it out of the usual 'recent' list
        remember(f"Nibbled grass #{i}", "", 0)
    now = time.time()
    db.x("INSERT INTO goals(ts,title,why,steps,updated) VALUES(?,?,?,?,?)",
         (now - 2 * DAY, "Study the moon", "it glows", "build a telescope, watch craters", now))
    text = brain.context(vitals.load())
    assert "Tycho" in text
    assert "started 2 days ago" in text
    assert old


def test_recap_waits_for_a_real_absence_then_shows_what_happened():
    t0 = time.time() - 6 * 3600
    recap.seen(t0)  # dad looked in six hours ago
    assert recap.for_dad(t0 + 60)["show"] is False  # still the same visit
    db.x("INSERT INTO creations(ts,kind,title,filename) VALUES(?,?,?,?)", (t0 + 3600, "poem", "Moon song", "x.md"))
    db.x("INSERT INTO goals(ts,title,why,updated,status) VALUES(?,?,?,?,?)",
         (t0 + 7200, "Build a telescope", "to see the moon", t0 + 7200, "active"))
    r = recap.for_dad()  # dad is back
    assert r["show"] is True
    assert [c["title"] for c in r["made"]] == ["Moon song"]
    assert [g["title"] for g in r["new_goals"]] == ["Build a telescope"]
    assert r["away"].endswith("hours")


def test_no_recap_when_nothing_happened():
    recap.seen(time.time() - 5 * 3600)
    assert recap.for_dad()["show"] is False
