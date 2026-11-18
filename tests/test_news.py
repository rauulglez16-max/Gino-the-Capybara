"""Gino's daily headline: gentle news only, once a day, and what he makes of it is up to him."""
import datetime as dt
import random

import pytest

from gino import brain, config, db, news, tools, vitals

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Science</title>
<item><title>Leonid meteor shower to peak on Tuesday night</title>
  <description>&lt;p&gt;The Leonids, known for bright and &lt;b&gt;fast&lt;/b&gt; meteors, peak this week.&lt;/p&gt;</description>
  <link>https://example.org/leonids</link></item>
<item><title>Scientists reveal a hidden snakebite crisis killing thousands a year</title>
  <description>Venomous bites are deadlier than thought.</description><link>https://example.org/snakes</link></item>
<item><title>Election results announced after a tense night</title><link>https://example.org/vote</link></item>
<item><title>Short</title></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Good news</title>
<entry><title>Glowworms shine again in a meadow after 100 years</title>
  <link rel="alternate" href="https://example.org/glowworms"/>
  <summary>A volunteer raised glowworm larvae in his garden shed.</summary></entry>
<entry><title>Sniffer dogs find invasive plants</title><link href="http://not-https.example/dogs"/></entry>
</feed>"""

MORNING = dt.datetime(2026, 11, 18, 9, 30)


@pytest.fixture
def news_on(monkeypatch):
    monkeypatch.setattr(config, "NEWS_ON", True)
    monkeypatch.setattr(config, "NEWS_FEEDS", "")


def fake_fetch(calls=None):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        if "positive" in url or "goodnews" in url:
            return ATOM
        if "bbc" in url:
            raise OSError("feed is down")
        return RSS
    return fetch


def test_parses_rss_and_atom():
    rss = news.parse(RSS, "Science")
    assert rss[0] == {"title": "Leonid meteor shower to peak on Tuesday night",
                      "summary": "The Leonids, known for bright and fast meteors, peak this week.",
                      "link": "https://example.org/leonids", "source": "Science"}
    atom = news.parse(ATOM, "Good")
    assert atom[0]["link"] == "https://example.org/glowworms"
    assert atom[1]["link"] == ""  # only https links are kept
    assert news.parse(b"<not xml", "x") == []


@pytest.mark.parametrize("title", [
    "Scientists reveal a hidden snakebite crisis killing up to 513,000 people a year",
    "Type 2 diabetes breakthrough as 54% achieve remission in just 6 months",
    "Less than 42 minutes of bright daylight linked to higher dementia risk",
    "Scientists confirm global warming is accelerating faster than ever recorded",
    "Man's Halloween Skeletons Prove Perfect Treat to Woman Battling Breast Cancer",
    "Burnham says climate consensus 'gone' but pledges 'new era of leadership'",
    "'It can kill us': Kenyans fear impact of El Niño with floods predicted",
    "Your Halloween Horoscope Advice: 'Free Will Astrology'",
    "Honey bees are bullying other bees, scientists discover",
    "Election results announced after a tense night",
])
def test_heavy_headlines_never_reach_him(title):
    assert not news.gentle({"title": title, "summary": ""})


@pytest.mark.parametrize("title", [
    "Astronauts just gave the International Space Station a powerful upgrade",
    "Glowworms Shine Again in the UK from Larvae Reared in Garden Shed",
    "Whale Festival Kicks Off Celebrating the Return of the Right Whale",
    "SpaceX successfully catches top of huge Starship rocket for first time",
    "This golden tree coral was too strange for any known family",
])
def test_gentle_headlines_get_through(title):
    assert news.gentle({"title": title, "summary": ""})


def test_pick_skips_heavy_seen_and_short():
    items = news.parse(RSS, "S") + news.parse(ATOM, "G")
    for seed in range(20):
        got = news.pick(items, seen={"sniffer dogs find invasive plants"}, rng=random.Random(seed))
        assert got["title"] in ("Leonid meteor shower to peak on Tuesday night",
                                "Glowworms shine again in a meadow after 100 years")
    assert news.pick(news.parse(RSS, "S")[1:]) is None


def test_once_a_day_and_not_before_morning(news_on):
    calls = []
    assert news.refresh(MORNING.replace(hour=4), fake_fetch(calls)) is None and calls == []
    first = news.refresh(MORNING, fake_fetch(calls))
    assert first and news.gentle(first)
    n = len(calls)
    assert news.refresh(MORNING.replace(hour=15), fake_fetch(calls))["title"] == first["title"]
    assert len(calls) == n  # no second trip to the feeds today
    assert any("heard a headline" in e["text"] for e in db.q("SELECT text FROM events"))
    # tomorrow brings a different headline
    second = news.refresh(MORNING + dt.timedelta(days=1), fake_fetch(calls))
    assert second and second["title"] != first["title"]


def test_unreachable_feeds_retry_later(news_on, monkeypatch):
    def down(url):
        raise OSError("no internet")
    assert news.refresh(MORNING, down) is None
    calls = []
    assert news.refresh(MORNING.replace(hour=10), fake_fetch(calls)) is None and calls == []  # too soon
    monkeypatch.setattr(news.time, "time", lambda: db.get("news_tried")["ts"] + 4 * 3600)
    assert news.refresh(MORNING.replace(hour=13), fake_fetch(calls))


def test_off_switch(monkeypatch):
    monkeypatch.setattr(config, "NEWS_ON", False)
    assert news.refresh(MORNING, fake_fetch()) is None
    assert "ponder_news" not in {t["name"] for t in tools.all_tools()}


def test_headline_in_his_turn_and_his_own_take(news_on, monkeypatch):
    monkeypatch.setattr(brain, "local_now", lambda: MORNING)
    item = news.refresh(MORNING, fake_fetch())
    body = vitals.load()
    ctx = news.context_lines(MORNING)
    assert item["title"] in ctx and "you decide" in ctx and "not a message to you" in ctx
    assert "ponder_news" in {t["name"] for t in tools.all_tools()}
    assert "Put your thought" in tools.run("ponder_news", {}, body)
    out = tools.run("ponder_news", {"thought": "I'd love to watch shooting stars from my pond.", "topic": "Stars",
                                    "became": "a painting"}, body)
    assert "Saved" in out
    mem = db.q("SELECT text,tags,importance FROM memories")[0]
    assert item["title"] in mem["text"] and mem["tags"] == "the news, stars" and mem["importance"] == 3
    assert "You already thought about it" in news.context_lines(MORNING)
    log = news.recent()
    assert log[0]["became"] == "a painting" and log[0]["title"] == item["title"]
    # pondering again the same day replaces, not duplicates, the day's entry
    tools.run("ponder_news", {"thought": "Still thinking about it."}, body)
    assert len(news.recent()) == 1


def test_no_headline_no_pondering(news_on):
    assert "no headline" in news.ponder(vitals.load(), {"thought": "hm"}, MORNING)
    assert news.context_lines(MORNING) == ""


def test_custom_feeds(monkeypatch):
    monkeypatch.setattr(config, "NEWS_FEEDS", "https://www.example.org/rss, http://insecure.example/feed, nonsense")
    assert news.feeds() == [("example.org", "https://www.example.org/rss")]
