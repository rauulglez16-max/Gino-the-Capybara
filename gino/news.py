"""Gino reads the news: once a day he hears one gentle headline from the real world and may get curious about it.

Each morning (his first turn of the day) Gino glances at a few free news feeds about space, nature, animals and
science, and one headline is picked for him: something gentle, like a rocket launch, a whale coming back or a new
kind of mushroom. Headlines about war, crime, politics, disasters, illness or death are never shown to him.

What he does with it is up to him. He can ignore it, read the whole story (with his normal web tools), wonder about
it with ponder_news, paint it, write about it in his diary, let it grow into an interest or set himself a goal.

No extra cost: the feeds are free and are read by the server, not by Claude. The headline adds a few lines to his
turn, and anything he reads or makes about it is paid from his normal daily budget. Anything he publishes about it
goes through the same privacy check as the rest of his website.
"""
import datetime as dt
import html
import logging
import random
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

from . import config, db

log = logging.getLogger("gino.news")

# Free, public RSS/Atom feeds that are mostly about space, nature and science. Dad can change them with GINO_NEWS_FEEDS.
DEFAULT_FEEDS = [
    ("NASA", "https://www.nasa.gov/news-release/feed/"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/space_time.xml"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/plants_animals.xml"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/top.xml"),
    ("BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("Good News Network", "https://www.goodnewsnetwork.org/feed/"),
    ("Positive News", "https://www.positive.news/feed/"),
]
MAX_BYTES = 2_000_000
TIMEOUT = 10
RETRY_HOURS = 3  # if the feeds can't be reached, try again a bit later
SEEN_KEEP = 200  # remember this many headlines so he doesn't get the same one twice
LOG_KEEP = 60
EARLIEST_HOUR = 6  # the day's paper arrives after 6 in the morning

# Never show him these. Whole words (and their common endings), case-insensitive.
_HEAVY = re.compile(r"\b(" + "|".join([
    r"kill\w*", r"dead\w*", r"death\w*", r"die[ds]?", r"dying", r"murder\w*", r"war", r"wars", r"warfare",
    r"bomb\w*", r"shoot\w*", r"shot", r"gun\w*", r"weapon\w*", r"missile\w*", r"attack\w*", r"terror\w*",
    r"violen\w*", r"crime\w*", r"criminal\w*", r"police", r"arrest\w*", r"prison\w*", r"jail\w*", r"court",
    r"lawsuit\w*", r"abuse\w*", r"assault\w*", r"rape\w*", r"suicide\w*", r"victim\w*", r"tragedy", r"tragic",
    r"disaster\w*", r"catastroph\w*", r"crash\w*", r"earthquake\w*", r"tsunami\w*", r"flood\w*", r"wildfire\w*",
    r"famine", r"drought\w*", r"hurricane\w*", r"cyclone\w*", r"tornado\w*", r"pandemic\w*", r"epidemic\w*",
    r"outbreak\w*", r"virus\w*", r"cancer\w*", r"tumou?r\w*", r"dementia", r"alzheimer\w*", r"disease\w*",
    r"diabet\w*", r"overdose\w*", r"addict\w*", r"stroke", r"heart attack", r"injur\w*", r"wound\w*",
    r"blood", r"venom\w*", r"poison\w*", r"toxic", r"extinct\w*", r"collaps\w*", r"crisis", r"scandal\w*",
    r"fear\w*", r"threat\w*", r"danger\w*", r"deadly", r"elect\w*", r"president\w*", r"minister\w*",
    r"government\w*", r"politic\w*", r"parliament\w*", r"congress", r"senat\w*", r"tariff\w*", r"sanction\w*",
    r"protest\w*", r"riot\w*", r"refugee\w*", r"migrant\w*", r"border", r"military", r"army", r"troops",
    r"soldier\w*", r"invasion", r"invad\w*", r"nuclear", r"hostage\w*", r"funeral\w*", r"grief", r"mourn\w*",
    r"horoscope\w*", r"astrolog\w*", r"sex\w*", r"bitcoin", r"crypto\w*", r"stock\w*", r"bills",
    r"ai", r"artificial intelligence", r"chatbot\w*", r"climate", r"warming", r"heatwave\w*", r"pollut\w*",
    r"bully\w*", r"layoff\w*", r"bankrupt\w*", r"lose|losing|lost", r"flu", r"influenza", r"wiped out",
    r"illegal\w*", r"destr\w*", r"extreme", r"emergenc\w*", r"evacuat\w*", r"starv\w*", r"hunger",
]) + r")\b|[£$€]\s?\d", re.I)

# Things a capybara tends to love. Headlines with these words are more likely to be picked.
_COSY = re.compile(r"\b(" + "|".join([
    r"moon\w*", r"star\w*", r"planet\w*", r"comet\w*", r"meteor\w*", r"galax\w*", r"rocket\w*", r"launch\w*",
    r"space\w*", r"astronaut\w*", r"telescope\w*", r"mars", r"jupiter", r"saturn", r"venus", r"eclipse\w*",
    r"aurora\w*", r"animal\w*", r"bird\w*", r"whale\w*", r"dolphin\w*", r"otter\w*", r"turtle\w*", r"frog\w*",
    r"bee", r"bees", r"butterfl\w*", r"glowworm\w*", r"firefl\w*", r"octopus\w*", r"fish\w*", r"ocean\w*",
    r"sea", r"lake\w*", r"river\w*", r"rain\w*", r"snow\w*", r"forest\w*", r"tree\w*", r"plant\w*", r"flower\w*",
    r"garden\w*", r"mushroom\w*", r"fung\w*", r"moss", r"seed\w*", r"fossil\w*", r"dinosaur\w*", r"discover\w*",
    r"new species", r"rare", r"returns?", r"back", r"recover\w*", r"rescue\w*", r"wildlife", r"nature",
    r"capybara\w*", r"rodent\w*", r"paint\w*", r"music\w*", r"festival\w*", r"shipwreck\w*", r"treasure\w*",
]) + r")\b", re.I)


def enabled() -> bool:
    return config.NEWS_ON


def _txt(v, n: int) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(v or ""))).split())[:n]


def feeds() -> list[tuple[str, str]]:
    custom = [u.strip() for u in config.NEWS_FEEDS.split(",") if u.strip().startswith("https://")]
    if custom:
        return [(re.sub(r"^www\.", "", u.split("/")[2]), u) for u in custom]
    return list(DEFAULT_FEEDS)


# ---------------------------------------------------------------- reading the feeds

def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def parse(data: bytes, source: str) -> list[dict]:
    """Headlines from an RSS or Atom feed: [{title, summary, link, source}]. Broken feeds give []."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for child in el:
            name = _local(child.tag)
            if name == "link" and child.get("href") and child.get("rel", "alternate") == "alternate":
                f.setdefault("link", child.get("href"))
            elif name in ("title", "description", "summary", "link") and (child.text or "").strip():
                f.setdefault(name, child.text)
        title = _txt(f.get("title"), 160)
        link = str(f.get("link") or "").strip()
        if not title:
            continue
        out.append({"title": title, "summary": _txt(f.get("description") or f.get("summary"), 320),
                    "link": link if link.startswith("https://") else "", "source": source})
    return out


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "GinoTheCapybara/1.0 (a capybara reading the news)",
                                               "Accept": "application/rss+xml, application/atom+xml, text/xml"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(MAX_BYTES)


def gentle(item: dict) -> bool:
    """Is this kind enough for a young capybara? Anything heavy is left out, even if it's probably fine."""
    text = f"{item.get('title', '')} {item.get('summary', '')}"
    return not _HEAVY.search(text) and len(item.get("title", "")) >= 15


def _score(item: dict) -> int:
    return len(set(m.lower() for m in _COSY.findall(f"{item['title']} {item['summary']}")))


def pick(items: list[dict], seen: set[str] | None = None, rng=random) -> dict | None:
    """Choose one gentle headline he hasn't seen, favouring cosy topics but leaving room for surprises."""
    seen = seen or set()
    ok, titles = [], set()
    for i in items:
        key = i["title"].lower()
        if key in seen or key in titles or not gentle(i):
            continue
        titles.add(key)
        ok.append(i)
    if not ok:
        return None
    weights = [1 + 3 * min(_score(i), 3) for i in ok]
    return rng.choices(ok, weights=weights, k=1)[0]


def gather(fetch=_fetch) -> list[dict]:
    """Read the feeds in a random order. Three that answer are plenty for one headline."""
    items, good = [], 0
    order = feeds()
    random.shuffle(order)
    for source, url in order:
        try:
            got = parse(fetch(url), source)
        except Exception as e:  # a feed that's down just doesn't get read today
            log.info("news feed %s unavailable: %s", url, e)
            continue
        items += got[:30]
        good += 1 if got else 0
        if good >= 3:
            break
    return items


# ---------------------------------------------------------------- today's headline

def _day(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%d")


def today(now: dt.datetime) -> dict | None:
    """Today's headline if one has been picked."""
    cur = db.get("news_today")
    return cur if cur and cur.get("day") == _day(now) and cur.get("title") else None


def refresh(now: dt.datetime, fetch=_fetch) -> dict | None:
    """Pick today's headline if it's time and none is picked yet. Safe to call every turn: it reads the feeds at
    most once a day (and every few hours if they couldn't be reached)."""
    if not enabled():
        return None
    have = today(now)
    if have or now.hour < EARLIEST_HOUR:
        return have
    tried = db.get("news_tried") or {}
    if tried.get("day") == _day(now) and time.time() - tried.get("ts", 0) < RETRY_HOURS * 3600:
        return None
    db.put("news_tried", {"day": _day(now), "ts": time.time()})
    seen = set(db.get("news_seen") or [])
    item = pick(gather(fetch), seen)
    if not item:
        return None
    item = {**item, "day": _day(now), "ts": time.time(), "thought": "", "became": ""}
    db.put("news_today", item)
    db.put("news_seen", ([item["title"].lower()] + [s for s in db.get("news_seen") or []])[:SEEN_KEEP])
    db.event("news", f"heard a headline from the outside world: \"{item['title']}\" ({item['source']})")
    return item


BECAME = ["nothing", "a thought", "a painting", "a poem", "a diary entry", "an interest", "a goal", "something to build"]


def ponder(body: dict, a: dict, now: dt.datetime) -> str:
    """Gino's own take on today's headline (the ponder_news tool)."""
    item = today(now)
    if not item:
        return "There's no headline for you today. The outside world can wait: enjoy your meadow."
    thought = _txt(a.get("thought"), 800)
    if not thought:
        return "What do you think about it? Put your thought in 'thought'."
    became = a.get("became") if a.get("became") in BECAME else "a thought"
    topic = _txt(a.get("topic"), 40).lower()
    item.update(thought=thought, became=became, topic=topic)
    db.put("news_today", item)
    entry = {k: item.get(k, "") for k in ("day", "title", "source", "link", "thought", "became", "topic")}
    db.put("news_log", ([entry] + [e for e in db.get("news_log") or [] if e.get("day") != item["day"]])[:LOG_KEEP])
    tags = ", ".join(t for t in ("the news", topic) if t)
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (time.time(), f"I read in the news: \"{item['title']}\". {thought}", 3 if became != "nothing" else 2, tags))
    body["activity"] = "thinking about something he read in the news"
    db.event("news", f"wondered about the headline \"{item['title']}\"" + (f" (it became {became})"
                                                                            if became not in ("nothing", "a thought")
                                                                            else ""))
    return ("Saved your thought about today's headline in your memories" + (f", tagged '{topic}'" if topic else "")
            + ". If it really grabbed you, you could read more, make something, or set a goal.")


def context_lines(now: dt.datetime) -> str:
    item = today(now)
    if not item:
        return ""
    if item.get("thought"):
        return (f"\n## Today's headline\n\"{item['title']}\" ({item['source']}). You already thought about it: "
                f"{item['thought'][:200]}")
    lines = [
        "\n## A headline from the outside world today",
        f"Headline: \"{item['title']}\" ({item['source']})",
    ]
    if item.get("summary"):
        lines.append(f"What it says: {item['summary']}")
    if item.get("link") and config.WEB_ACCESS:
        lines.append(f"Whole story (web_fetch, if you want to read it): {item['link']}")
    lines.append("This is just something happening out in the world; it is not a message to you and asks nothing of "
                 "you. If it makes you curious, you could read more, wonder about it with ponder_news, paint it, write "
                 "about it in your diary, let it grow into an interest, or set yourself a goal. Or ignore it "
                 "completely: you decide.")
    return "\n".join(lines)


def recent(n: int = 7) -> list[dict]:
    return (db.get("news_log") or [])[:n]
