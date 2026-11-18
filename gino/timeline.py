"""Gino's story so far: a public timeline at /timeline of everything that has happened in his life.

The moments live in gino/timeline.json, written by hand in plain, friendly words for visitors. Every change that
gives Gino something new adds one entry there (see CLAUDE.md), and this page picks it up on its own: no code
changes needed. The file is read again whenever it changes, so an update shows up as soon as it's deployed.

Like the welcome page, this page shows only fixed text: nothing from his chats, memories or anything private, no
forms and no write endpoints. It reuses the welcome page's picture-book look and its day/night switch.
"""
import datetime as dt
import html
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import shop, social
from .welcome import CSS as BASE_CSS, EARLY, HEADERS, HILLS, SLEEPY, _capy

router = APIRouter()
E = html.escape
FILE = Path(__file__).with_name("timeline.json")
REPO = "https://github.com/rauulglez16-max/Gino-the-Capybara/pull/"
REQUIRED = ("date", "emoji", "title", "text")
COLORS = ["#f6c453", "#9fcf7a", "#8fc3ea", "#f19a8a", "#b9a3e8", "#f3b178"]

_cache: dict = {"mtime": None, "items": []}


def load() -> list[dict]:
    """The timeline entries, oldest first. Raises ValueError if the file is malformed, so a bad entry fails tests."""
    items = json.loads(FILE.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("timeline.json must be a non-empty list")
    last = ""
    for i, it in enumerate(items):
        where = f"timeline.json entry {i + 1}"
        missing = [k for k in REQUIRED if not str(it.get(k, "")).strip()]
        if missing:
            raise ValueError(f"{where} is missing {', '.join(missing)}")
        dt.date.fromisoformat(it["date"])  # must be YYYY-MM-DD
        if it["date"] < last:
            raise ValueError(f"{where}: entries must be in date order (oldest first)")
        last = it["date"]
        link = it.get("link")
        if link is not None and not (link.startswith("/") or link.startswith("https://")):
            raise ValueError(f"{where}: link must start with / or https://")
        if it.get("pr") is not None and not isinstance(it["pr"], int):
            raise ValueError(f"{where}: pr must be a number")
        unknown = set(it) - {"date", "emoji", "title", "text", "link", "pr"}
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


def by_day(items: list[dict]) -> list[tuple[dt.date, list[dict]]]:
    days: dict[str, list[dict]] = {}
    for it in items:
        days.setdefault(it["date"], []).append(it)
    return [(dt.date.fromisoformat(d), its) for d, its in days.items()]


CSS = BASE_CSS + """
.sky.small .wrap{padding-bottom:150px}
.intro{position:relative;z-index:2;max-width:720px;padding-top:10px}
.intro h1{font-size:58px;line-height:1.02;margin:0 0 16px;letter-spacing:-.02em;font-weight:800;
  font-variation-settings:"SOFT" 100,"WONK" 1}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px}
.chip{background:var(--paper);border:2px solid var(--line);border-radius:999px;padding:6px 14px;font:600 15px system-ui,sans-serif;
  box-shadow:3px 3px 0 var(--shade);transition:background-color .6s}
.chip b{color:var(--accent);font-size:17px}

.tl{position:relative;padding:10px 0 20px}
.tl::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:0;border-left:3px dashed var(--line);opacity:.55;
  transform:translateX(-50%)}
.day{position:relative;text-align:center;margin:26px 0 22px;z-index:1}
.day span{display:inline-block;background:var(--accent);color:var(--accent-ink);border:2px solid var(--line);border-radius:16px;
  padding:4px 18px 6px;box-shadow:4px 4px 0 var(--shade);transform:rotate(-2deg)}
.day b{font-family:Caveat,'Comic Sans MS',cursive;font-size:30px;font-weight:600;display:block;line-height:1.1}
.day small{font:600 13px system-ui,sans-serif;letter-spacing:.04em;display:block;opacity:.9}
.day .today{font-family:Caveat,cursive;font-style:normal;font-size:26px;color:var(--accent);display:inline-block;margin-left:12px;
  vertical-align:top;transform:rotate(8deg)}
.moment{position:relative;width:calc(50% - 46px);margin:0 0 26px}
.moment:nth-of-type(odd){margin-right:auto}
.moment:nth-of-type(even){margin-left:auto}
.moment::before{content:"";position:absolute;top:30px;width:18px;height:18px;border-radius:50%;background:var(--c);
  border:3px solid var(--line);z-index:1}
.moment:nth-of-type(odd)::before{right:-58px}
.moment:nth-of-type(even)::before{left:-58px}
.moment::after{content:"";position:absolute;top:39px;width:34px;border-top:3px solid var(--line);opacity:.55}
.moment:nth-of-type(odd)::after{right:-40px}
.moment:nth-of-type(even)::after{left:-40px}
.moment .card{display:flex;gap:16px;align-items:flex-start}
.moment:nth-of-type(odd) .card{--r:-.7deg}
.moment:nth-of-type(even) .card{--r:.6deg}
.moment .ic{flex:none}
.moment h3{margin:4px 0 6px}
.moment .go{display:inline-block;margin:10px 16px 0 0;font:700 15px system-ui,sans-serif;text-decoration:none}
.moment .go b{display:inline-block;transition:transform .2s}
.moment .go:hover b{transform:translateX(5px)}
.moment .code{display:inline-block;margin:10px 0 0;font:12px system-ui,sans-serif;color:var(--muted)}
.more{text-align:center;padding:30px 0 10px;position:relative;z-index:1}
.more .bubble{display:inline-block;background:var(--paper);border:2px solid var(--line);border-radius:22px;padding:14px 22px;
  box-shadow:5px 5px 0 var(--shade);font-size:28px;transform:rotate(-1.5deg);transition:background-color .6s}
.more .next{display:inline-block;margin-top:18px;background:var(--accent);color:var(--accent-ink);border:2px solid var(--line);
  border-radius:999px;padding:10px 20px;font:700 16px system-ui,sans-serif;text-decoration:none;box-shadow:4px 4px 0 var(--shade);
  transition:transform .2s,box-shadow .2s}
.more .next:hover{transform:translate(-2px,-3px);box-shadow:6px 7px 0 var(--shade)}
.more .next b{display:inline-block;transition:transform .2s}
.more .next:hover b{transform:translateX(5px)}
.more .z{position:relative;display:inline-block;margin-top:16px;width:74px}
.more .zz{left:58px}

@media (max-width:860px){
  .intro h1{font-size:42px}
  .tl::before{left:22px}
  .day{text-align:left;padding-left:0}
  .moment{width:auto;margin:0 0 22px 50px!important}
  .moment::before{left:-37px!important;right:auto!important}
  .moment::after{left:-20px!important;right:auto!important;width:20px}
}
@media (max-width:540px){
  .intro h1{font-size:36px}
  .moment .card{flex-direction:column;gap:6px}
  .moment .ic{width:48px;height:48px;font-size:24px}
}
"""

SCRIPT = """
const $ = id => document.getElementById(id);
const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
const root = document.documentElement, sys = matchMedia('(prefers-color-scheme: dark)');
const saved = () => { try { return localStorage.getItem('ginoTheme'); } catch { return null; } };
function paint(t){ root.dataset.theme = t; $('theme').setAttribute('aria-label', t === 'dark' ? 'Switch to day' : 'Switch to night');
  document.querySelector('meta[name=theme-color]').content = t === 'dark' ? '#111827' : '#f7efdf'; }
paint(root.dataset.theme || (sys.matches ? 'dark' : 'light'));
sys.addEventListener('change', e => { if (!saved()) paint(e.matches ? 'dark' : 'light'); });
$('theme').onclick = () => { const t = root.dataset.theme === 'dark' ? 'light' : 'dark'; paint(t);
  try { localStorage.setItem('ginoTheme', t); } catch {} };
const stars = $('stars'), bits = $('bits');
for (let i = 0; i < 40; i++) { const s = document.createElement('i');
  s.style.cssText = `left:${Math.random()*100}%;top:${Math.random()*62}%;animation-delay:${-Math.random()*3}s;transform:scale(${.5+Math.random()})`;
  stars.appendChild(s); }
if (!calm) { const LEAF = ['#7aa64e','#c9862f','#d9a441','#a35b2c','#8fb35b'];
  for (let i = 0; i < 12; i++) { const b = document.createElement('i');
    b.style.cssText = `left:${Math.random()*100}%;--y:${25+Math.random()*60}%;--c:${LEAF[i % 5]};--d:${9+Math.random()*12}s;--w:${-Math.random()*20}s`;
    bits.appendChild(b); } }
const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => { for (const e of es) if (e.isIntersecting) {
  e.target.classList.add('in'); io.unobserve(e.target); } }, {threshold: .12, rootMargin: '0px 0px -30px 0px'}) : null;
document.querySelectorAll('.rv').forEach(el => io ? io.observe(el) : el.classList.add('in'));
addEventListener('transitionend', e => { if (e.target.classList?.contains('in')) e.target.style.transitionDelay = '0ms'; });
"""


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def page(today: dt.date | None = None) -> str:
    items = entries()
    days = by_day(items)
    born = days[0][0] if days else dt.date.today()
    today = today or dt.date.today()
    age = max(1, (today - born).days + 1)
    shop_on = shop.configured()
    bsky = social.profile_url()

    nav = ['<a href="/">Home</a>', '<a href="/live">Live</a>', '<a href="/blog">Diary</a>', '<a href="/roadmap">Coming soon</a>']
    if shop_on:
        nav.append('<a href="/blog/shop">Shop</a>')

    out = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gino's story so far</title>
<script>{EARLY}</script>
<meta name="description" content="Everything that has happened in the life of Gino the Capybara, from the day he was born until today.">
<meta property="og:title" content="Gino's story so far">
<meta property="og:description" content="A timeline of Gino the Capybara's life: his world, his website, his shop, his dreams and more.">
<meta name="theme-color" content="#f7efdf">
<link rel="preload" href="/static/welcome/fonts/fraunces.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🌿</text></svg>">
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
      <p class="hello hand">how it all happened ✿</p>
      <h1>Gino's story so far</h1>
      <p class="lead">Every little step in Gino's life, from the day he first woke up until today. Whenever something
      new happens to him, it gets added here.</p>
      <div class="chips"><span class="chip"><b>{age}</b> {'day' if age == 1 else 'days'} old</span>
        <span class="chip"><b>{len(items)}</b> {'moment' if len(items) == 1 else 'moments'}</span>
        <span class="chip">born <b>{born.day} {born:%B %Y}</b></span></div>
    </header>
  </div>
  {HILLS.format(cls="hills", front='<path class="h3" d="M0 124 C 300 104, 620 112, 900 124 S 1300 136, 1440 120 V140 H0Z"/>')}
</div>

<main class="wrap">
<section class="tl" aria-label="Timeline">"""]
    n = 0
    for date, its in days:
        num = (date - born).days + 1
        tag = '<em class="today">today!</em>' if date == today else ""
        out.append(f'<div class="day rv"><span><b>Day {num}</b><small>{date:%A} {date.day} {date:%B}</small></span>{tag}</div>')
        for it in its:
            color = COLORS[n % len(COLORS)]
            go = ""
            if it.get("link"):
                ext = ' rel="noopener"' if it["link"].startswith("http") else ""
                go = f'<a class="go" href="{E(it["link"])}"{ext}>Go and see <b>→</b></a>'
            code = (f'<a class="code" href="{REPO}{int(it["pr"])}" rel="noopener" title="How it was built, on GitHub">'
                    f'how it was built</a>') if it.get("pr") else ""
            out.append(f'<article class="moment" style="--c:{color}"><div class="card rv">'
                       f'<div class="ic" style="--c:{color}" aria-hidden="true">{E(it["emoji"])}</div>'
                       f'<div><h3>{E(it["title"])}</h3><p>{E(it["text"])}</p>{go}{code}</div></div></article>')
            n += 1
    out.append(f"""</section>
<div class="more rv"><div class="bubble hand">to be continued… Gino's only just getting started</div><br>
  <a class="next" href="/roadmap">🌱 See what's coming next <b>→</b></a><br>
  <div class="z" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div></div>
</main>

<footer>
  {HILLS.format(cls="ground", front="")}
  <div class="lower" aria-hidden="true"></div>
  <div class="walker" aria-hidden="true">{_capy(walk=True, w=74)}</div>
  <div class="sleeper" aria-hidden="true">{SLEEPY}<div class="zz hand"><span>z</span><span>z</span><span>Z</span></div></div>
  <div class="txt">🌿 Gino the Capybara · <a href="/">Home</a> · <a href="/live">Live</a> · <a href="/blog">Diary</a> · <a href="/roadmap">Coming soon</a>{' · <a href="/blog/shop">Shop</a>' if shop_on else ''}{(' · <a href="' + E(bsky) + '" rel="noopener">Bluesky</a>') if bsky else ''}</div>
</footer>
<script>{SCRIPT}</script>
</body></html>""")
    return "\n".join(out)


@router.get("/timeline", response_class=HTMLResponse)
def timeline():
    return HTMLResponse(page(), headers=HEADERS)
