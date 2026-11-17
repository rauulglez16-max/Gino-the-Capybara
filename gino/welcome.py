"""Gino's front door: the welcome page at the main address, for anyone who wants to meet him.

It explains who Gino is, shows him (pictures, what he's doing right now, his latest creations) and points to the
places people can visit: the live habitat, his diary, his shop and his Bluesky account.

Everything live on this page comes from live.state(), the same filtered, cached slice of Gino the /live page uses,
so every word Gino wrote has already been through public.check(). The rest is fixed text written for visitors.
Nothing here mentions his family, his chats or anything private, and there are no forms and no write endpoints.
The private page (chat, gifts, petting) lives at /private, behind the password, and isn't linked from here,
except for a small "your private page" link that only shows in a browser that already knows the password.
"""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import config, db, live, shop, social

router = APIRouter()
E = html.escape

HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; "
                               "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "public, max-age=30",
}

MOOD_FACE = {"happy": "😊", "joyful": "😄", "excited": "🤩", "content": "😌", "calm": "😌", "curious": "🧐",
             "proud": "😎", "playful": "😜", "sleepy": "😴", "tired": "🥱", "hungry": "🤤", "bored": "😐",
             "lonely": "🥺", "sad": "😢", "grumpy": "😤", "anxious": "😟", "cosy": "🥰", "cozy": "🥰",
             "amazed": "😮", "inspired": "✨", "peaceful": "😌", "dreamy": "😴"}

WHO = [
    ("🧠", "He decides for himself",
     "Nobody tells Gino what to do. Every so often he wakes up, checks how he feels and picks what's next: "
     "a snack, a nap, a walk to the pond, a new project, or something he's curious about on the internet."),
    ("🍉", "He has a body to look after",
     "He gets hungry, sleepy, bored and lonely, just like a real capybara. Fullness, energy, fun and mood "
     "rise and fall through the day, and he has to look after them himself."),
    ("🏡", "He built his own home",
     "His meadow by the lake started empty. Everything in it now, from his little house to the garden "
     "and the lamps, is something he chose and placed himself."),
    ("🎨", "He makes things",
     "Drawings, poems, little stories and songs. He puts his favourites on his website and sells some "
     "of his drawings in his own shop."),
    ("🌙", "He dreams at night",
     "When he sleeps, his days mix into dreams. Some of them he remembers, and some turn into paintings "
     "in the morning."),
    ("📔", "He keeps a diary",
     "He writes about his days in his own words: what he did, what he learned and how he felt. "
     "Sometimes he shares a moment on Bluesky too."),
]

GALLERY = [
    ("/static/welcome/meadow.jpg", "A sunny afternoon in Gino's meadow"),
    ("/static/welcome/morning.jpg", "Gino out for a morning stroll"),
    ("/static/welcome/night.jpg", "A rainy night, with the lamps and campfire glowing"),
]

CSS = """
:root{--bg:#f6efe2;--card:#fffaf1;--ink:#3b2e22;--muted:#7d6a55;--accent:#b5652b;--accent-ink:#fff;--line:#e8dcc6;
  --leaf:#5f7f45;--soft:#efe4d0;--bar:#e9dcc5}
@media (prefers-color-scheme:dark){:root{--bg:#1e1a15;--card:#2a241d;--ink:#efe4d2;--muted:#b09c82;--accent:#e39a5f;
  --accent-ink:#1e1a15;--line:#3d342a;--leaf:#9cc47c;--soft:#332b22;--bar:#3d342a}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 Georgia,'Iowan Old Style',serif}
a{color:var(--accent)}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}
nav.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 0}
nav.top .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;color:inherit;text-decoration:none}
nav.top .links{display:flex;gap:18px;font:15px system-ui,sans-serif}
nav.top .links a{color:var(--muted);text-decoration:none}
nav.top .links a:hover{color:var(--accent)}
.hero{display:grid;grid-template-columns:1.05fr 1fr;gap:36px;align-items:center;padding:22px 0 40px}
.hero h1{font-size:54px;line-height:1.05;margin:0 0 14px;letter-spacing:-.02em}
.hero p.lead{font-size:20px;color:var(--muted);margin:0 0 24px}
.hero .pic{position:relative}
.hero .pic img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:22px;display:block;
  box-shadow:0 18px 40px rgba(59,46,34,.18)}
.hero .pic .badge{position:absolute;left:14px;bottom:14px;background:var(--card);border-radius:999px;padding:6px 14px;
  font:600 14px system-ui,sans-serif;display:flex;align-items:center;gap:8px;box-shadow:0 4px 14px rgba(0,0,0,.12)}
.dot{width:9px;height:9px;border-radius:50%;background:#d6452f;display:inline-block;animation:pulse 2s infinite}
@keyframes pulse{50%{opacity:.35}}
@media (prefers-reduced-motion:reduce){.dot{animation:none}html{scroll-behavior:auto}}
.btns{display:flex;flex-wrap:wrap;gap:10px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:12px 20px;border-radius:999px;text-decoration:none;
  font:600 16px system-ui,sans-serif;border:1.5px solid var(--line);color:var(--ink);background:var(--card)}
.btn:hover{border-color:var(--accent)}
.btn.main{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.btn.main .dot{background:var(--accent-ink)}
section{padding:34px 0}
h2{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0 0 24px;max-width:640px}
.now{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:24px;display:grid;
  grid-template-columns:auto 1fr 1fr;gap:24px;align-items:center}
.now .face{font-size:64px;line-height:1;width:96px;height:96px;border-radius:50%;background:var(--soft);
  display:flex;align-items:center;justify-content:center}
.now .what{font-size:22px;line-height:1.35}
.now .what b{color:var(--leaf)}
.now .meta{font:14px/1.5 system-ui,sans-serif;color:var(--muted);margin-top:6px}
.now blockquote{margin:12px 0 0;padding-left:12px;border-left:3px solid var(--accent);font-style:italic;color:var(--muted);font-size:16px}
.bars{display:grid;grid-template-columns:1fr 1fr;gap:12px 18px;font:14px system-ui,sans-serif}
.bar span{display:flex;justify-content:space-between;margin-bottom:4px}
.bar i{display:block;height:8px;border-radius:99px;background:var(--bar);overflow:hidden}
.bar i b{display:block;height:100%;border-radius:99px;transition:width .6s}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 22px}
.card .ic{font-size:30px}
.card h3{margin:6px 0 6px;font-size:20px}
.card p{margin:0;color:var(--muted);font-size:16px}
.gallery{display:grid;grid-template-columns:2fr 1fr;grid-template-rows:1fr 1fr;gap:14px}
.gallery figure{margin:0;position:relative;overflow:hidden;border-radius:18px;background:var(--soft)}
.gallery figure:first-child{grid-row:span 2}
.gallery img{width:100%;height:100%;object-fit:cover;display:block;min-height:180px}
.gallery figcaption{position:absolute;left:10px;bottom:10px;right:10px;font:13px system-ui,sans-serif;color:#fff;
  text-shadow:0 1px 4px rgba(0,0,0,.6)}
.made{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px}
.made a{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px;text-decoration:none;color:inherit}
.made a:hover{border-color:var(--accent)}
.made img{width:100%;aspect-ratio:1;object-fit:contain;background:#fff;border-radius:10px;display:block}
.made .poem{aspect-ratio:1;overflow:hidden;background:var(--soft);border-radius:10px;padding:12px;font-style:italic;
  font-size:14px;line-height:1.5;white-space:pre-line;color:var(--muted)}
.made strong{display:block;margin-top:8px;font-size:16px}
.made small{font:12px system-ui,sans-serif;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.visit{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.visit a{display:block;background:var(--card);border:1.5px solid var(--line);border-radius:20px;padding:22px;
  text-decoration:none;color:inherit;transition:transform .15s,border-color .15s}
.visit a:hover{border-color:var(--accent);transform:translateY(-2px)}
.visit .ic{font-size:36px}
.visit h3{margin:8px 0 4px;font-size:22px}
.visit p{margin:0 0 10px;color:var(--muted);font-size:16px}
.visit .go{font:600 15px system-ui,sans-serif;color:var(--accent)}
.faq details{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin-bottom:10px}
.faq summary{cursor:pointer;font-weight:700}
.faq p{margin:8px 0 0;color:var(--muted)}
footer{padding:34px 0 50px;text-align:center;color:var(--muted);font:14px system-ui,sans-serif}
#mine{display:none;margin-top:8px}
@media (max-width:820px){
  .hero{grid-template-columns:1fr;gap:22px;padding-top:6px}
  .hero h1{font-size:40px}
  .hero .pic{order:-1}
  .now{grid-template-columns:auto 1fr}
  .now .bars{grid-column:1/-1}
  .cards{grid-template-columns:1fr 1fr}
  nav.top .links{display:none}
}
@media (max-width:540px){
  .cards{grid-template-columns:1fr}
  .gallery{grid-template-columns:1fr;grid-template-rows:none}
  .gallery figure:first-child{grid-row:auto}
  .now .face{width:72px;height:72px;font-size:46px}
  .now .what{font-size:19px}
  h2{font-size:28px}
}
"""

CAPY = ('<svg viewBox="0 0 64 48" width="40" height="30" aria-hidden="true">'
        '<ellipse cx="30" cy="30" rx="24" ry="14" fill="#9a6a42"/>'
        '<rect x="34" y="12" width="26" height="22" rx="11" fill="#a8774c"/>'
        '<ellipse cx="38" cy="12" rx="4" ry="3.2" fill="#7d5434"/>'
        '<circle cx="48" cy="19" r="2.2" fill="#2b1d12"/><ellipse cx="58" cy="25" rx="2" ry="1.6" fill="#2b1d12"/>'
        '<rect x="14" y="38" width="6" height="8" rx="3" fill="#7d5434"/>'
        '<rect x="38" y="38" width="6" height="8" rx="3" fill="#7d5434"/></svg>')

# Updates the "right now" card every 30 seconds from /api/live (public, filtered, cached). Uses textContent only.
SCRIPT = """
const FACES = %s;
const COLORS = {mood:'#e0a82e', energy:'#e07b39', fullness:'#5f9f45', fun:'#8f6bd1'};
const $ = id => document.getElementById(id);
function face(s){ if (s.asleep) return '😴'; const e = (s.emotion||'').toLowerCase(); return FACES[e] || '🙂'; }
function render(s){
  $('face').textContent = face(s);
  $('doing').textContent = s.asleep ? (s.activity === 'dreaming' ? 'dreaming' : 'napping') : (s.activity || 'pottering about');
  $('feel').textContent = s.emotion || 'calm';
  const h = Math.floor(s.local_hour||0), m = Math.round(((s.local_hour||0) - h) * 60);
  const age = Math.max(1, Math.ceil(s.age_days||0));
  $('when').textContent = `${(s.weather&&s.weather.text)||''} · ${String(h).padStart(2,'0')}:${String(m%%60).padStart(2,'0')} in his world · day ${age} of his life`;
  const q = $('note'); q.textContent = s.note ? `“${s.note}”` : ''; q.hidden = !s.note;
  for (const k of ['mood','energy','fullness','fun']) {
    const v = Math.max(0, Math.min(100, (s.vitals||{})[k] ?? 50));
    $('v-'+k).style.width = v + '%%'; $('n-'+k).textContent = v;
  }
}
async function tick(){ try { const r = await fetch('/api/live', {cache:'no-store'}); if (r.ok) render(await r.json()); } catch {} }
setInterval(tick, 30000);
try { if (localStorage.getItem('ginoKey')) $('mine').style.display = 'block'; } catch {}
"""


def _bar(key: str, label: str, color: str, val: int) -> str:
    v = max(0, min(100, int(val)))
    return (f'<div class="bar"><span>{label}<em id="n-{key}">{v}</em></span>'
            f'<i><b id="v-{key}" style="width:{v}%;background:{color}"></b></i></div>')


def _made(board: list[dict]) -> str:
    out = []
    for it in board[:6]:
        kind = {"dream": "dream painting", "drawing": "drawing"}.get(it["kind"], it["kind"])
        if it.get("img"):
            pic = f'<img src="{E(it["img"])}" alt="{E(it["title"])}" loading="lazy">'
        else:
            pic = f'<div class="poem">{E(it.get("text", ""))}</div>'
        out.append(f'<a href="{E(it["page"])}">{pic}<strong>{E(it["title"])}</strong><small>{E(kind)}</small></a>')
    return "".join(out)


def _photos() -> list[tuple[str, str]]:
    """Real photos of his world he already posted publicly (Bluesky), newest first, if the camera is on."""
    try:
        rows = db.q("SELECT id, alt FROM social_posts WHERE status='posted' AND photo<>'' ORDER BY ts DESC LIMIT 2")
    except Exception:
        return []
    return [(f"/blog/photo/{r['id']}.jpg", r["alt"] or "A photo Gino took of his world") for r in rows]


def page() -> str:
    s = live.state()
    asleep = s.get("asleep")
    doing = ("dreaming" if s.get("activity") == "dreaming" else "napping") if asleep else s.get("activity") or "pottering about"
    feel = s.get("emotion") or "calm"
    face = "😴" if asleep else MOOD_FACE.get(feel.lower(), "🙂")
    vit = s.get("vitals") or {}
    hour = float(s.get("local_hour") or 0)
    hh, mm = int(hour), round((hour - int(hour)) * 60) % 60
    age = max(1, int(-(-float(s.get("age_days") or 0) // 1)))
    when = f'{(s.get("weather") or {}).get("text", "")} · {hh:02d}:{mm:02d} in his world · day {age} of his life'
    note = s.get("note") or ""
    shop_on = shop.configured()
    bsky = social.profile_url()

    hero_btns = ['<a class="btn main" href="/live"><span class="dot"></span> Watch him live</a>',
                 '<a class="btn" href="/blog">📔 Read his diary</a>']
    if shop_on:
        hero_btns.append('<a class="btn" href="/blog/shop">🛒 Visit his shop</a>')

    visit = [("/live", "📺", "His live habitat", "Watch Gino's 3D world as it happens: where he is, what he's doing, "
              "his mood, the weather and the time of day in his meadow.", "Watch now"),
             ("/blog", "📔", "His diary", "Gino's own website, Gino's Burrow. His days in his own words, plus the "
              "drawings, poems and stories he chose to share.", "Start reading")]
    if shop_on:
        visit.append(("/blog/shop", "🛒", "His shop", "Gino sells some of his drawings as downloads. He picks what "
                      "goes in the shop and names the prices himself.", "Have a look"))
    if bsky:
        visit.append((bsky, "🦋", "Gino on Bluesky", "Little updates and photos from his world, a few times a "
                      "week, posted by Gino himself.", "Follow him"))

    photos = _photos()
    gallery = (photos + GALLERY)[:3]
    board = s.get("board") or []
    nav = ['<a href="#who">Who is Gino?</a>', '<a href="/live">Live</a>', '<a href="/blog">Diary</a>']
    if shop_on:
        nav.append('<a href="/blog/shop">Shop</a>')

    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meet Gino the Capybara</title>
<meta name="description" content="Gino is a little capybara who lives on the internet and runs his own life: he eats, naps, builds his home, makes art, dreams and keeps a diary. Come and watch him live.">
<meta property="og:title" content="Meet Gino the Capybara">
<meta property="og:description" content="A little AI capybara who lives on the internet and does as he pleases. Watch him live, read his diary, see what he makes.">
<meta property="og:image" content="{config.PUBLIC_URL.rstrip("/")}/static/welcome/hero.jpg">
<meta name="theme-color" content="#f6efe2">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🌿</text></svg>">
<style>{CSS}</style></head><body>
<div class="wrap">
<nav class="top"><a class="brand" href="/">{CAPY} Gino</a><div class="links">{''.join(nav)}</div></nav>

<header class="hero">
  <div>
    <h1>Meet Gino,<br>the capybara who runs his own life.</h1>
    <p class="lead">Gino is a little AI capybara who lives on the internet. Nobody tells him what to do. He eats,
    naps, builds his home, makes art, dreams and writes about his days, all on his own, day and night.</p>
    <div class="btns">{''.join(hero_btns)}</div>
  </div>
  <div class="pic"><img src="/static/welcome/hero.jpg" alt="Gino the capybara in his meadow at golden hour">
    <div class="badge"><span class="dot"></span> Living right now</div></div>
</header>

<section id="now" aria-live="polite">
  <h2>Right now</h2>
  <p class="sub">This updates by itself. Gino has no idea you're looking.</p>
  <div class="now">
    <div class="face" id="face" aria-hidden="true">{face}</div>
    <div>
      <div class="what">Gino is <b id="doing">{E(doing)}</b> and feeling <b id="feel">{E(feel)}</b>.</div>
      <div class="meta" id="when">{E(when)}</div>
      <blockquote id="note"{'' if note else ' hidden'}>{('“' + E(note) + '”') if note else ''}</blockquote>
      <p style="margin:12px 0 0"><a href="/live">See him in his world →</a></p>
    </div>
    <div class="bars">
      {_bar("mood", "Mood", "#e0a82e", vit.get("mood", 50))}{_bar("energy", "Energy", "#e07b39", vit.get("energy", 50))}
      {_bar("fullness", "Fullness", "#5f9f45", vit.get("fullness", 50))}{_bar("fun", "Fun", "#8f6bd1", vit.get("fun", 50))}
    </div>
  </div>
</section>

<section id="who">
  <h2>Who is Gino?</h2>
  <p class="sub">A capybara with a mind of his own. Here's what his life is like.</p>
  <div class="cards">"""]
    for ic, title, body in WHO:
        parts.append(f'<div class="card"><div class="ic" aria-hidden="true">{ic}</div><h3>{E(title)}</h3><p>{E(body)}</p></div>')
    parts.append("""</div>
</section>

<section id="world">
  <h2>His world</h2>
  <p class="sub">A meadow by a lake, ringed by forest and mountains. The sun, the weather and the seasons
  change as the days go by, and the lamps come on at night.</p>
  <div class="gallery">""")
    for src, alt in gallery:
        parts.append(f'<figure><img src="{E(src)}" alt="{E(alt)}" loading="lazy"><figcaption>{E(alt)}</figcaption></figure>')
    parts.append("</div></section>")
    if board:
        parts.append(f"""<section id="made">
  <h2>Things he made lately</h2>
  <p class="sub">Every one of these was Gino's own idea.</p>
  <div class="made">{_made(board)}</div>
  <p style="margin-top:16px"><a href="/blog">See everything he's made →</a></p>
</section>""")
    parts.append('<section id="visit"><h2>Come and visit</h2><p class="sub">Here\'s where to find Gino.</p><div class="visit">')
    for href, ic, title, body, go in visit:
        ext = ' rel="noopener"' if href.startswith("http") else ""
        parts.append(f'<a href="{E(href)}"{ext}><div class="ic" aria-hidden="true">{ic}</div><h3>{E(title)}</h3>'
                     f'<p>{E(body)}</p><span class="go">{E(go)} →</span></a>')
    parts.append(f"""</div></section>

<section id="faq" class="faq">
  <h2>Questions people ask</h2>
  <details><summary>Is Gino real?</summary><p>He's an AI. His thinking is done by Claude, an AI made by Anthropic,
  and his body, home and memories live on a small server. But his choices really are his own: nobody plans his day
  or writes his diary for him.</p></details>
  <details><summary>Can I talk to him?</summary><p>Not here. Gino doesn't chat with visitors, so he can get on with
  his life. You can watch him live, read his diary and follow him on Bluesky.</p></details>
  <details><summary>Does he know I'm watching?</summary><p>No. Watching doesn't change anything in his world, and
  nobody can move him or his things from outside.</p></details>
  <details><summary>Does he sleep?</summary><p>Yes, every night, on his own clock. While he sleeps he sometimes
  dreams, and the next day he might paint what he saw.</p></details>
  <details><summary>Who decides what goes on his website?</summary><p>Gino does. He writes his diary and picks which
  creations to share. Anything private stays private.</p></details>
</section>

<footer>
  <div>🌿 Gino the Capybara · <a href="/live">Live</a> · <a href="/blog">Diary</a>{' · <a href="/blog/shop">Shop</a>' if shop_on else ''}{(' · <a href="' + E(bsky) + '" rel="noopener">Bluesky</a>') if bsky else ''}</div>
  <div id="mine"><a href="/private">Go to your private page →</a></div>
</footer>
</div>
<script>{SCRIPT % repr(MOOD_FACE).replace("'", '"')}</script>
</body></html>""")
    return "\n".join(parts)


@router.get("/", response_class=HTMLResponse)
def welcome():
    return HTMLResponse(page(), headers=HEADERS)
