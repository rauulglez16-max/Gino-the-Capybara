"""Gino's public website: a diary of his days and pages for the things he makes, readable by anyone, no password.

Only what Gino deliberately publishes (the `posts` table) shows up here. His private page, memories, private
journal and chats with dad never do. Everything he publishes goes through `check()` first, which turns away
anything about dad, keys, passwords or contact details.
"""
import html
import re
import time
import datetime as dt

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from . import config, db

MAX_BODY = 20000
MAX_PAGES = 300
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9\-]{0,59}")

# ---------------------------------------------------------------- safety

_FAMILY = re.compile(r"\b(dad|dads|daddy|dada|father|fathers|papa|pops)\b", re.I)
_SECRETY = re.compile(r"sk-ant-|\b[sr]k_(?:live|test)_|anthropic_api_key|gino_password|app[\s_-]?password|x-gino-key|api[\s_-]?key|password|passcode", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+\d[\d\s\-()]{7,}\d")


def _secrets() -> list[str]:
    import os
    vals = [os.environ.get("ANTHROPIC_API_KEY", ""), os.environ.get("ANTHROPIC_AUTH_TOKEN", ""), config.PASSWORD,
            config.BLUESKY_APP_PASSWORD, config.STRIPE_KEY]
    return [v for v in vals if v and len(v) >= 4]


def _dad_sentences() -> list[str]:
    """Sentences dad wrote in chat, so they can't be quoted on the public site."""
    out = []
    for r in db.q("SELECT text FROM chat WHERE sender='dad' ORDER BY ts DESC LIMIT 300"):
        for s in re.split(r"[.!?\n]+", r["text"]):
            s = " ".join(s.lower().split())
            if len(s) >= 24:
                out.append(s)
    return out


def check(*texts: str) -> str | None:
    """Return why this can't be published, or None if it's fine to show the whole world."""
    text = "\n".join(t or "" for t in texts)
    low = text.lower()
    name = (config.DAD_NAME or "").strip()
    if (len(name) >= 2 and re.search(rf"\b{re.escape(name)}\b", text, re.I)) or _FAMILY.search(text):
        return ("Your public website must never mention your dad (not his name, not 'dad', nothing about him). "
                "He is private. Rewrite it about yourself and your world.")
    if any(s.lower() in low for s in _secrets()) or _SECRETY.search(text):
        return "That looks like it mentions a key or a password. Those are private: leave them out completely."
    if _EMAIL.search(text) or _PHONE.search(text):
        return "No email addresses or phone numbers on your public website. Take them out."
    flat = " ".join(low.split())
    if any(s in flat for s in _dad_sentences()):
        return "That quotes your private chats. Chats stay private: write it in your own words about yourself."
    return None


# ---------------------------------------------------------------- storage

def _local_now() -> dt.datetime:
    from .brain import local_now  # imported late: brain imports tools, which imports this file
    return local_now()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "page"


def today() -> str:
    return _local_now().strftime("%Y-%m-%d")


def write_diary(entry: str, title: str = "", replace: bool = False) -> str:
    entry, title = str(entry or "").strip(), str(title or "").strip()[:120]
    if not entry:
        return "Nothing to publish: the entry was empty."
    problem = check(entry, title)
    if problem:
        return "Not published. " + problem
    day, now = today(), time.time()
    row = db.q("SELECT id,title,body FROM posts WHERE kind='diary' AND slug=?", (day,))
    if row and not replace:
        stamp = _local_now().strftime("%H:%M")
        body = f"{row[0]['body']}\n\n### {stamp}\n\n{entry}"
    else:
        body = entry
    if len(body) > MAX_BODY:
        return f"Too long for one day ({len(body)} characters, the limit is {MAX_BODY}). Keep it shorter."
    if row:
        db.x("UPDATE posts SET body=?, title=?, updated=? WHERE id=?", (body, title or row[0]["title"], now, row[0]["id"]))
        what = "replaced" if replace else "added to"
    else:
        db.x("INSERT INTO posts(ts,updated,kind,slug,title,body) VALUES(?,?,?,?,?,?)",
             (now, now, "diary", day, title or _local_now().strftime("%A %d %B"), body))
        what = "published"
    db.event("public", f"{what} today's public diary on his website")
    return f"Today's diary {what} on your public website at /blog/diary/{day}."


def write_page(title: str, content: str, slug: str = "", summary: str = "", creation_id: int | None = None) -> str:
    title, content = str(title or "").strip()[:120], str(content or "").strip()
    summary = str(summary or "").strip()[:300]
    if not title or not (content or creation_id):
        return "A page needs a title and some content."
    slug = _slug(str(slug or title))
    if not SLUG_RE.fullmatch(slug):
        return "That page name won't work as a web address. Try simpler words."
    if len(content) > MAX_BODY:
        return f"Too long ({len(content)} characters, the limit is {MAX_BODY})."
    creation = None
    if creation_id:
        rows = db.q("SELECT id,kind,title,filename,note FROM creations WHERE id=?", (int(creation_id),))
        if not rows:
            return f"You don't have a creation #{creation_id}."
        creation = rows[0]
    problem = check(title, content, summary, _creation_text(creation) if creation else "")
    if problem:
        return "Not published. " + problem
    now = time.time()
    row = db.q("SELECT id FROM posts WHERE kind='page' AND slug=?", (slug,))
    if row:
        db.x("UPDATE posts SET title=?, body=?, summary=CASE WHEN ?='' THEN summary ELSE ? END, "
             "creation_id=COALESCE(?, creation_id), updated=? WHERE id=?",
             (title, content, summary, summary, creation["id"] if creation else None, now, row[0]["id"]))
        db.event("public", f"updated the page '{title}' on his website")
        return f"Updated your page at /blog/page/{slug}."
    if db.q("SELECT COUNT(*) AS n FROM posts WHERE kind='page'")[0]["n"] >= MAX_PAGES:
        return f"Your website already has {MAX_PAGES} pages. Take one down first (unpublish)."
    db.x("INSERT INTO posts(ts,updated,kind,slug,title,body,summary,creation_id) VALUES(?,?,?,?,?,?,?,?)",
         (now, now, "page", slug, title, content, summary, creation["id"] if creation else None))
    db.event("public", f"published a page on his website: {title}")
    return f"Published your page at /blog/page/{slug}."


def unpublish(kind: str, slug: str) -> str:
    kind = "diary" if kind == "diary" else "page"
    rows = db.q("SELECT id,title FROM posts WHERE kind=? AND slug=?", (kind, str(slug)))
    if not rows:
        return f"There's no {kind} '{slug}' on your website."
    db.x("DELETE FROM posts WHERE id=?", (rows[0]["id"],))
    db.event("public", f"took '{rows[0]['title']}' off his website")
    return f"Took '{rows[0]['title']}' off your website."


def _creation_text(c: dict) -> str:
    if c["kind"] == "svg":
        return c["title"]
    path = config.DATA_DIR / "creations" / c["filename"]
    return c["title"] + "\n" + (path.read_text(encoding="utf-8") if path.exists() else "")


def context_lines() -> str:
    """What Gino sees about his website each turn."""
    diary = db.q("SELECT 1 FROM posts WHERE kind='diary' AND slug=?", (today(),))
    pages = db.q("SELECT slug,title FROM posts WHERE kind='page' ORDER BY updated DESC LIMIT 8")
    n = db.q("SELECT COUNT(*) AS n FROM posts")[0]["n"]
    lines = ["\n## Your public website (anyone can read it)",
             "Today's diary: " + ("written (you can add more as the day goes on)." if diary
                                  else "not written yet. Write it with public_diary when you have something to tell.")]
    if pages:
        lines.append("Pages: " + "; ".join(f"{p['title']} (/{p['slug']})" for p in pages))
    lines.append(f"{n} posts in total.")
    return "\n".join(lines)


# ---------------------------------------------------------------- tiny, safe markdown

def _inline(s: str) -> str:
    s = html.escape(s, quote=True)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s)\"]+|/blog[^\s)\"]*)\)",
               r'<a href="\2" rel="nofollow noopener">\1</a>', s)
    return s


def md(text: str) -> str:
    """Markdown-ish to HTML. Everything is escaped first, so nothing Gino writes can run as code."""
    out, para, items, code = [], [], [], None
    ordered = False

    def flush():
        nonlocal para, items
        if para:
            out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>")
            para = []
        if items:
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{tag}>")
            items = []

    for line in (text or "").replace("\r", "").split("\n"):
        if code is not None:
            if line.strip().startswith("```"):
                out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        st = line.strip()
        if st.startswith("```"):
            flush()
            code = []
        elif not st:
            flush()
        elif m := re.match(r"(#{1,4})\s+(.*)", st):
            flush()
            lvl = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
        elif m := re.match(r"([-*]|\d+[.)])\s+(.*)", st):
            if para:
                flush()
            is_ol = m.group(1)[0].isdigit()
            if items and is_ol != ordered:
                flush()
            ordered = is_ol
            items.append(m.group(2))
        elif st.startswith(">"):
            flush()
            out.append(f"<blockquote>{_inline(st.lstrip('> '))}</blockquote>")
        elif re.fullmatch(r"-{3,}|\*{3,}", st):
            flush()
            out.append("<hr>")
        else:
            if items:
                flush()
            para.append(st)
    if code is not None:
        out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
    flush()
    return "\n".join(out)


def _excerpt(text: str, n: int = 220) -> str:
    plain = re.sub(r"(?m)^#+\s*\d{1,2}:\d{2}\s*$", " ", text or "")
    plain = re.sub(r"[#*_`>\[\]]|\(https?://[^)]*\)", "", plain)
    plain = " ".join(plain.split())
    return plain if len(plain) <= n else plain[:n].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------- web pages

CAPY = ('<svg class="face" viewBox="0 0 64 48" width="58" height="44" aria-hidden="true">'
        '<ellipse cx="30" cy="30" rx="24" ry="14" fill="#9a6a42"/>'
        '<rect x="34" y="12" width="26" height="22" rx="11" fill="#a8774c"/>'
        '<ellipse cx="38" cy="12" rx="4" ry="3.2" fill="#7d5434"/>'
        '<circle cx="48" cy="19" r="2.2" fill="#2b1d12"/><ellipse cx="58" cy="25" rx="2" ry="1.6" fill="#2b1d12"/>'
        '<rect x="14" y="38" width="6" height="8" rx="3" fill="#7d5434"/>'
        '<rect x="38" y="38" width="6" height="8" rx="3" fill="#7d5434"/></svg>')

router = APIRouter()
E = html.escape

CSS = """
:root{--bg:#f6efe2;--card:#fffaf1;--ink:#3b2e22;--muted:#8a7660;--accent:#b5652b;--line:#e8dcc6;--leaf:#5f7f45}
@media (prefers-color-scheme:dark){:root{--bg:#1e1a15;--card:#2a241d;--ink:#efe4d2;--muted:#b09c82;--accent:#e39a5f;--line:#3d342a;--leaf:#9cc47c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 Georgia,'Iowan Old Style',serif}
a{color:var(--accent)}
.wrap{max-width:760px;margin:0 auto;padding:28px 16px 60px}
header.top{display:flex;align-items:center;gap:14px;margin-bottom:22px}
header.top .face{flex:none}
header.top h1{margin:0;font-size:30px;letter-spacing:-.01em}
header.top h1 a{color:inherit;text-decoration:none}
header.top p{margin:2px 0 0;color:var(--muted);font-size:15px}
.now{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin-bottom:26px;
  font:15px/1.5 system-ui,sans-serif;color:var(--muted)}
.now b{color:var(--leaf)}
h2.sec{font:600 13px/1 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:34px 0 12px}
.post{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 22px;margin-bottom:14px}
.post h3{margin:0 0 4px;font-size:21px}
.post h3 a{color:inherit;text-decoration:none}
.post h3 a:hover{color:var(--accent)}
.meta{font:13px/1.4 system-ui,sans-serif;color:var(--muted)}
.post p.ex{margin:8px 0 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;text-decoration:none;color:inherit}
.tile img{width:100%;aspect-ratio:1;object-fit:contain;background:#fff;border-radius:10px;display:block;margin-bottom:8px}
.tile strong{display:block}
article{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 28px}
article h1{margin:0 0 4px;font-size:30px;line-height:1.2}
article .body{margin-top:18px}
article .body h2,article .body h3,article .body h4{margin:1.4em 0 .3em;line-height:1.25}
article img.art{width:100%;max-width:520px;display:block;margin:18px auto;background:#fff;border-radius:12px}
pre{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto;font-size:14px}
code{font-family:ui-monospace,Menlo,monospace;font-size:.9em}
blockquote{margin:1em 0;padding-left:14px;border-left:3px solid var(--accent);color:var(--muted)}
.creation{white-space:pre-wrap;font-style:italic;background:var(--bg);border-radius:12px;padding:16px 18px;margin:16px 0}
nav.pager{display:flex;justify-content:space-between;margin-top:18px;font:15px system-ui,sans-serif}
footer{margin-top:40px;text-align:center;color:var(--muted);font:13px system-ui,sans-serif}
.empty{color:var(--muted);font-style:italic}
.post img.shot{width:100%;border-radius:10px;display:block;margin-bottom:10px}
@media (max-width:520px){article{padding:20px 18px}header.top h1{font-size:25px}}
"""

HEADERS = {
    "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; "
                               "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "public, max-age=60",
}


def _page(title: str, inner: str, desc: str = "") -> HTMLResponse:
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc or "The diary of Gino, a capybara who lives on the internet.")}">
<link rel="alternate" type="application/rss+xml" title="Gino's diary" href="/blog/feed.xml">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🌿</text></svg>">
<style>{CSS}</style></head><body><div class="wrap">
<header class="top">{CAPY}<div><h1><a href="/blog">Gino's Burrow</a></h1>
<p>A capybara writing about his days, what he learns and what he makes. Written by Gino himself.</p></div></header>
{inner}
<footer>Everything here was written by Gino, an AI capybara who lives on a little server and does as he pleases.</footer>
</div></body></html>"""
    return HTMLResponse(doc, headers=HEADERS)


def _when(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%d %b %Y")


def _now_line() -> str:
    try:
        from . import vitals
        body = vitals.load()
        asleep = vitals.is_asleep(body)
        doing = "napping 💤" if asleep else (body.get("activity") or "pottering about")
        feel = body.get("emotion") or "calm"
        if check(doing, feel):
            return '<div class="now">Gino is out and about. <a href="/live">Watch him live</a></div>'
        return f'<div class="now">Right now Gino is <b>{E(doing)}</b> and feeling <b>{E(feel)}</b>. <a href="/live">Watch him live</a></div>'
    except Exception:
        return ""


def _art(c: dict | None) -> str:
    if not c:
        return ""
    if c["kind"] == "svg":
        return f'<img class="art" src="/blog/art/{c["id"]}.svg" alt="{E(c["title"])}">'
    path = config.DATA_DIR / "creations" / c["filename"]
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if c["kind"] == "code":
        return f"<pre><code>{E(text)}</code></pre>"
    return f'<div class="creation">{E(text)}</div>'


def _creation(cid) -> dict | None:
    if not cid:
        return None
    rows = db.q("SELECT id,kind,title,filename FROM creations WHERE id=?", (cid,))
    return rows[0] if rows else None


@router.get("/blog", response_class=HTMLResponse)
def home():
    diary = db.q("SELECT slug,title,body,ts FROM posts WHERE kind='diary' ORDER BY slug DESC LIMIT 30")
    pages = db.q("SELECT p.slug,p.title,p.summary,p.body,p.ts,p.creation_id,c.kind AS ckind FROM posts p "
                 "LEFT JOIN creations c ON c.id=p.creation_id WHERE p.kind='page' ORDER BY p.ts DESC LIMIT 60")
    parts = [_now_line()]
    from . import shop  # imported late: shop imports this file
    if shop.configured():
        parts.append('<div class="now">🛒 Gino has a shop! <a href="/blog/shop">See the drawings he\'s selling</a></div>')
    parts.append('<h2 class="sec">Diary</h2>')
    if diary:
        for d in diary:
            parts.append(f'<div class="post"><h3><a href="/blog/diary/{d["slug"]}">{E(d["title"])}</a></h3>'
                         f'<div class="meta">{d["slug"]}</div><p class="ex">{E(_excerpt(d["body"]))}</p></div>')
    else:
        parts.append('<p class="empty">Gino hasn\'t written his first diary entry yet. Check back soon!</p>')
    if pages:
        parts.append('<h2 class="sec">Things Gino made and wrote</h2><div class="grid">')
        for p in pages:
            img = (f'<img src="/blog/art/{p["creation_id"]}.svg" alt="">' if p["ckind"] == "svg" else "")
            parts.append(f'<a class="tile" href="/blog/page/{p["slug"]}">{img}<strong>{E(p["title"])}</strong>'
                         f'<span class="meta">{_when(p["ts"])}</span>'
                         f'<p class="meta">{E(p["summary"] or _excerpt(p["body"], 110))}</p></a>')
        parts.append("</div>")
    from . import social  # imported late: social imports this file
    posts = social.recent_public(5)
    if posts:
        parts.append(f'<h2 class="sec">On Bluesky</h2>')
        for sp in posts:
            link = social.web_link(sp["uri"])
            when = dt.datetime.fromtimestamp(sp["ts"]).strftime("%d %b %Y, %H:%M")
            pic = (f'<img class="shot" src="/blog/photo/{sp["id"]}.jpg" alt="{E(sp["alt"])}" loading="lazy">'
                   if sp["photo"] else "")
            parts.append(f'<div class="post">{pic}<p class="ex" style="margin:0">{E(sp["text"])}</p><div class="meta">'
                         + (f'<a href="{E(link)}" rel="nofollow noopener">{when}</a>' if link else when)
                         + "</div></div>")
        if social.profile_url():
            parts.append(f'<p class="meta"><a href="{E(social.profile_url())}" rel="nofollow noopener">'
                         f'Follow Gino on Bluesky</a></p>')
    return _page("Gino's Burrow", "\n".join(parts))


@router.get("/blog/diary/{day}", response_class=HTMLResponse)
def diary_day(day: str):
    if not DATE_RE.fullmatch(day):
        raise HTTPException(404)
    rows = db.q("SELECT slug,title,body FROM posts WHERE kind='diary' AND slug=?", (day,))
    if not rows:
        raise HTTPException(404, "No diary for that day.")
    d = rows[0]
    prev = db.q("SELECT slug FROM posts WHERE kind='diary' AND slug<? ORDER BY slug DESC LIMIT 1", (day,))
    nxt = db.q("SELECT slug FROM posts WHERE kind='diary' AND slug>? ORDER BY slug LIMIT 1", (day,))
    pager = ('<nav class="pager"><span>' + (f'<a href="/blog/diary/{prev[0]["slug"]}">← {prev[0]["slug"]}</a>' if prev else "")
             + "</span><span>" + (f'<a href="/blog/diary/{nxt[0]["slug"]}">{nxt[0]["slug"]} →</a>' if nxt else "")
             + "</span></nav>")
    inner = (f'<article><h1>{E(d["title"])}</h1><div class="meta">Diary · {day}</div>'
             f'<div class="body">{md(d["body"])}</div></article>{pager}')
    return _page(f"{d['title']} · Gino's diary", inner, _excerpt(d["body"], 160))


@router.get("/blog/page/{slug}", response_class=HTMLResponse)
def page(slug: str):
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(404)
    rows = db.q("SELECT title,body,summary,ts,updated,creation_id FROM posts WHERE kind='page' AND slug=?", (slug,))
    if not rows:
        raise HTTPException(404, "No such page.")
    p = rows[0]
    upd = f" · updated {_when(p['updated'])}" if p["updated"] - p["ts"] > 3600 else ""
    inner = (f'<article><h1>{E(p["title"])}</h1><div class="meta">{_when(p["ts"])}{upd}</div>'
             f'{_art(_creation(p["creation_id"]))}<div class="body">{md(p["body"])}</div></article>'
             '<nav class="pager"><a href="/blog">← all of Gino\'s things</a></nav>')
    return _page(f"{p['title']} · Gino's Burrow", inner, p["summary"] or _excerpt(p["body"], 160))


@router.get("/blog/art/{cid}.svg")
def art(cid: int):
    """A drawing, but only if Gino put it on a public page."""
    if not db.q("SELECT 1 FROM posts WHERE kind='page' AND creation_id=?", (cid,)):
        raise HTTPException(404)
    c = _creation(cid)
    if not c or c["kind"] != "svg":
        raise HTTPException(404)
    path = config.DATA_DIR / "creations" / c["filename"]
    if not path.exists():
        raise HTTPException(404)
    return Response(path.read_bytes(), media_type="image/svg+xml",
                    headers={**HEADERS, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.get("/blog/photo/{pid}.jpg")
def social_photo(pid: int):
    """A photo Gino posted on Bluesky (only ones he actually posted)."""
    rows = db.q("SELECT photo FROM social_posts WHERE id=? AND status='posted' AND photo!=''", (pid,))
    path = config.DATA_DIR / "photos" / f"{pid}.jpg"
    if not rows or not path.exists():
        raise HTTPException(404)
    return Response(path.read_bytes(), media_type="image/jpeg",
                    headers={**HEADERS, "Cache-Control": "public, max-age=86400"})


@router.get("/blog/feed.xml")
def feed():
    rows = db.q("SELECT kind,slug,title,body,updated FROM posts ORDER BY updated DESC LIMIT 30")
    items = "".join(
        f"<item><title>{E(r['title'])}</title><link>/blog/{r['kind']}/{r['slug']}</link>"
        f"<guid isPermaLink=\"false\">{r['kind']}-{r['slug']}</guid>"
        f"<pubDate>{dt.datetime.fromtimestamp(r['updated'], dt.timezone.utc):%a, %d %b %Y %H:%M:%S +0000}</pubDate>"
        f"<description>{E(_excerpt(r['body'], 400))}</description></item>" for r in rows)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Gino\'s Burrow</title>'
           '<link>/blog</link><description>The diary of Gino the capybara</description>' + items + "</channel></rss>")
    return Response(xml, media_type="application/rss+xml", headers={"Cache-Control": "public, max-age=300"})
