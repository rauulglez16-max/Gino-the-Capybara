"""What's coming next for Gino: a public "coming soon" page at /roadmap.

The plans live in gino/roadmap.json, written by hand in plain, friendly words for visitors. To change the page, edit
that file: add, remove or reorder items, or move one between "next", "soon" and "someday". When something is built,
remove it from roadmap.json and add it to timeline.json instead (see CLAUDE.md). No code changes needed: the file is
read again whenever it changes, so an update shows up as soon as it's deployed.

Like the timeline, this page shows only fixed text: nothing private, no forms and no write endpoints. It reuses the
welcome page's picture-book look and its day/night switch.
"""
import html
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import shop, social
from .timeline import CSS as TL_CSS, SCRIPT
from .welcome import EARLY, HEADERS, HILLS, SLEEPY, _capy

router = APIRouter()
E = html.escape
FILE = Path(__file__).with_name("roadmap.json")
REQUIRED = ("when", "emoji", "title", "text")
FIELDS = set(REQUIRED) | {"link"}
# Each group: (key in roadmap.json, sign emoji, heading, little note, colours for its cards)
GROUPS = [
    ("next", "🌱", "Next up", "being planted right now", ["#9fcf7a", "#f6c453", "#8fc3ea"]),
    ("soon", "🌿", "Coming soon", "growing nicely", ["#f19a8a", "#b9a3e8", "#f3b178", "#9fcf7a"]),
    ("someday", "🌳", "Someday", "still a dream", ["#8fc3ea", "#f6c453", "#b9a3e8", "#f19a8a"]),
]
WHEN = [g[0] for g in GROUPS]

_cache: dict = {"mtime": None, "items": []}


def load() -> list[dict]:
    """The plans, in file order. Raises ValueError if the file is malformed, so a bad item fails tests."""
    items = json.loads(FILE.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("roadmap.json must be a non-empty list")
    for i, it in enumerate(items):
        where = f"roadmap.json item {i + 1}"
        missing = [k for k in REQUIRED if not str(it.get(k, "")).strip()]
        if missing:
            raise ValueError(f"{where} is missing {', '.join(missing)}")
        if it["when"] not in WHEN:
            raise ValueError(f"{where}: when must be one of {', '.join(WHEN)}")
        link = it.get("link")
        if link is not None and not (link.startswith("/") or link.startswith("https://")):
            raise ValueError(f"{where}: link must start with / or https://")
        unknown = set(it) - FIELDS
        if unknown:
            raise ValueError(f"{where}: unknown field(s) {', '.join(sorted(unknown))}")
    return items


def entries() -> list[dict]:
    """load(), cached until the file changes. A broken file keeps the last good list instead of breaking the page."""
    try:
        m = FILE.stat().st_mtime
        if m != _cache["mtime"]:
            _cache["items"], _cache["mtime"] = load(), m
    except (OSError, ValueError):
        pass
    return _cache["items"]


CSS = TL_CSS + """
.path{position:relative;padding:10px 0 10px}
.stop{position:relative;margin:34px 0 10px}
.sign{display:flex;align-items:center;gap:14px;margin:0 0 22px}
.sign .post{font-size:40px;line-height:1;width:72px;height:72px;border-radius:50%;background:var(--paper);border:2px solid var(--line);
  display:grid;place-items:center;box-shadow:4px 4px 0 var(--shade);transition:background-color .6s;flex:none}
.sign h2{margin:0;font-size:38px}
.sign h2::after{width:90px;height:10px}
.sign .note{font-size:24px;color:var(--accent);display:inline-block;transform:rotate(-3deg);margin-left:4px}
.stop .cards{grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.stop .card h3{font-size:21px}
.stop.someday .card{border-style:dashed}
.stop.someday .card .ic{opacity:.85}
.tag{display:inline-block;margin-top:12px;font:700 12px system-ui,sans-serif;letter-spacing:.05em;text-transform:uppercase;
  color:var(--muted);border:1.5px solid currentColor;border-radius:999px;padding:2px 10px}
.stop.next .tag{color:var(--accent)}
.card .go{display:inline-block;margin:10px 0 0 10px;font:700 14px system-ui,sans-serif;text-decoration:none}
.trail{text-align:center;margin:8px 0 0;font-size:30px;letter-spacing:12px;opacity:.5}
.more p{max-width:560px;margin:14px auto 0;color:var(--muted)}
@media (max-width:540px){.sign h2{font-size:30px}.sign .post{width:58px;height:58px;font-size:32px}}
"""


def page() -> str:
    items = entries()
    shop_on = shop.configured()
    bsky = social.profile_url()
    nav = ['<a href="/">Home</a>', '<a href="/live">Live</a>', '<a href="/blog">Diary</a>',
           '<a href="/timeline">His story</a>']
    if shop_on:
        nav.append('<a href="/blog/shop">Shop</a>')
    count = {k: sum(1 for it in items if it["when"] == k) for k in WHEN}

    out = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coming soon for Gino</title>
<script>{EARLY}</script>
<meta name="description" content="What's coming next in the life of Gino the Capybara: new places, new friends and new things to make.">
<meta property="og:title" content="Coming soon for Gino">
<meta property="og:description" content="The things Gino the Capybara has coming up next: a museum, a friend, expeditions and more.">
<meta name="theme-color" content="#f7efdf">
<link rel="preload" href="/static/welcome/fonts/fraunces.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🌱</text></svg>">
<style>{CSS}</style></head><body>
<div class="sky small">
  <div class="stars" id="stars" aria-hidden="true"></div>
  <div class="orb" aria-hidden="true"></div>
  <div class="bits" id="bits" aria-hidden="true"></div>
  <div class="wrap">
    <nav class="top"><a class="brand" href="/">{_capy(w=46)} Gino</a>
      <div class="links">{''.join(nav)}
        <button id="theme" type="button" aria-label="Switch day or night"><span class="sun">☀️</span><span class="moon">🌙</span></button>
      </div></nav>
    <header class="intro">
      <p class="hello hand">what's coming up ✿</p>
      <h1>Coming soon for Gino</h1>
      <p class="lead">Some of the things on their way to Gino's life: new places to explore, new friends and new
      things to make. Some are nearly here, some are still just ideas.</p>
      <div class="chips"><span class="chip">🌱 <b>{count['next']}</b> next up</span>
        <span class="chip">🌿 <b>{count['soon']}</b> coming soon</span>
        <span class="chip">🌳 <b>{count['someday']}</b> someday</span></div>
    </header>
  </div>
  {HILLS.format(cls="hills", front='<path class="h3" d="M0 124 C 300 104, 620 112, 900 124 S 1300 136, 1440 120 V140 H0Z"/>')}
</div>

<main class="wrap">
<section class="path" aria-label="Coming soon">"""]
    for g, (key, sign, heading, note, colors) in enumerate(GROUPS):
        its = [it for it in items if it["when"] == key]
        if not its:
            continue
        if g:
            out.append('<div class="trail" aria-hidden="true">🐾 🐾 🐾</div>')
        out.append(f'<div class="stop {key}"><div class="sign rv"><span class="post" aria-hidden="true">{sign}</span>'
                   f'<div><h2>{E(heading)}</h2><span class="note hand">{E(note)}</span></div></div><div class="cards">')
        for i, it in enumerate(its):
            c = colors[i % len(colors)]
            go = ""
            if it.get("link"):
                ext = ' rel="noopener"' if it["link"].startswith("http") else ""
                go = f'<a class="go" href="{E(it["link"])}"{ext}>Have a look →</a>'
            out.append(f'<article class="card rv"><div class="ic" style="--c:{c}" aria-hidden="true">'
                       f'{E(it["emoji"])}</div><h3>{E(it["title"])}</h3><p>{E(it["text"])}</p>'
                       f'<span class="tag">{E(heading)}</span>{go}</article>')
        out.append('</div></div>')
    out.append(f"""</section>
<div class="more rv"><div class="bubble hand">plans can change… Gino has ideas of his own too</div>
  <p>Gino runs his own life, so some of the best things that happen to him won't be on any list. When something here
  arrives, it moves over to his story.</p>
  <a class="next" href="/timeline">🗺️ See his story so far <b>→</b></a><br>
  <div class="z" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div></div>
</main>

<footer>
  {HILLS.format(cls="ground", front="")}
  <div class="lower" aria-hidden="true"></div>
  <div class="walker" aria-hidden="true">{_capy(walk=True, w=74)}</div>
  <div class="sleeper" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div>
  <div class="txt">🌿 Gino the Capybara · <a href="/">Home</a> · <a href="/live">Live</a> · <a href="/blog">Diary</a> · <a href="/timeline">His story</a>{' · <a href="/blog/shop">Shop</a>' if shop_on else ''}{(' · <a href="' + E(bsky) + '" rel="noopener">Bluesky</a>') if bsky else ''}</div>
</footer>
<script>{SCRIPT}</script>
</body></html>""")
    return "\n".join(out)


@router.get("/roadmap", response_class=HTMLResponse)
def roadmap():
    return HTMLResponse(page(), headers=HEADERS)
