"""Gino's own art style, and the periods it goes through.

Two halves:
- What he says his style is: an art period he names himself ("my pond phase"), with the palette, symbols and
  shapes he's drawn to and why. He starts a new period whenever he feels his art has moved on.
- What his drawings actually show: every drawing is read for its colours and shapes (no AI call, just looking at
  the picture's code). Each turn he sees what his recent work looks like, so his style carries over from one
  drawing to the next, and if his drawings drift away from the period he named, he notices.

Every drawing is filed under the period it was made in. Visitors can browse the periods at /blog/periods, with
the drawings he has already chosen to show on his website.
"""
import colorsys
import json
import re
import time
from collections import Counter

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import config, db, public

router = APIRouter()
DAY = 86400
MIN_PERIOD_DAYS = 2  # a period is more than a mood: at least a couple of days long

NAMED = {"red": "#ff0000", "orange": "#ffa500", "gold": "#ffd700", "yellow": "#ffff00", "green": "#008000",
         "lime": "#00ff00", "teal": "#008080", "cyan": "#00ffff", "blue": "#0000ff", "navy": "#000080",
         "purple": "#800080", "violet": "#ee82ee", "pink": "#ffc0cb", "magenta": "#ff00ff", "brown": "#a52a2a",
         "white": "#ffffff", "black": "#000000", "gray": "#808080", "grey": "#808080", "coral": "#ff7f50",
         "salmon": "#fa8072", "tomato": "#ff6347", "skyblue": "#87ceeb", "indigo": "#4b0082", "olive": "#808000",
         "tan": "#d2b48c", "khaki": "#f0e68c", "crimson": "#dc143c", "turquoise": "#40e0d0", "lavender": "#e6e6fa"}
STOP = set("""with from into over under the and for its his my your a an of in on at to by this that night day
little big tiny study sketch drawing painting picture dream untitled number""".split())


# ---------------------------------------------------------------- reading a drawing

def _rgb(token: str) -> tuple[float, float, float] | None:
    t = token.strip().lower()
    if t in NAMED:
        t = NAMED[t]
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", t)
    if m:
        h = m.group(1)
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    m = re.fullmatch(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+).*\)", t)
    if m:
        return tuple(min(int(v), 255) / 255 for v in m.groups())
    m = re.fullmatch(r"hsla?\(\s*(-?[\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%.*\)", t)
    if m:
        h, s, light = float(m.group(1)) % 360 / 360, float(m.group(2)) / 100, float(m.group(3)) / 100
        return colorsys.hls_to_rgb(h, min(light, 1), min(s, 1))
    return None


def family(rgb: tuple[float, float, float]) -> str:
    """A colour in words: 'orange', 'deep blue' style families, simple enough to compare."""
    h, light, s = colorsys.rgb_to_hls(*rgb)
    hue = h * 360
    if light > 0.93:
        return "white"
    if light < 0.1:
        return "black"
    if s < 0.15:
        return "grey"
    if 15 <= hue < 45 and light < 0.4:
        return "brown"
    for top, name in ((15, "red"), (45, "orange"), (68, "yellow"), (160, "green"), (195, "teal"), (255, "blue"),
                      (290, "purple"), (345, "pink"), (360, "red")):
        if hue < top:
            return name
    return "red"


COLOUR_RE = re.compile(r"(?:fill|stroke|stop-color|flood-color|color)\s*[:=]\s*[\"']?\s*"
                       r"(#[0-9a-fA-F]{3,6}\b|(?:rgb|hsl)a?\([^)]*\)|[a-zA-Z]+)")


def measure(svg: str) -> tuple[Counter, Counter]:
    """(colour families, shape words) found in one drawing."""
    colours = Counter()
    for tok in COLOUR_RE.findall(svg or ""):
        rgb = _rgb(tok)
        if rgb:
            colours[family(rgb)] += 1
    s = svg or ""
    shapes = Counter()
    shapes["round shapes"] += len(re.findall(r"<(?:circle|ellipse)\b", s))
    shapes["blocks"] += len(re.findall(r"<rect\b", s))
    shapes["sharp lines"] += len(re.findall(r"<(?:polygon|polyline|line)\b", s))
    for d in re.findall(r"<path\b[^>]*\sd\s*=\s*[\"']([^\"']*)", s):
        shapes["curves" if re.search(r"[CcQqSsTtAa]", d) else "sharp lines"] += 1
    shapes["haze and blur"] += 2 * len(re.findall(r"<fe(?:GaussianBlur|Turbulence)\b", s))
    shapes["gradients"] += len(re.findall(r"<(?:linear|radial)Gradient\b", s))
    return colours, +shapes


def _read(c: dict) -> str:
    path = config.DATA_DIR / "creations" / c["filename"]
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def fingerprint(rows: list[dict]) -> dict:
    """What a set of drawings has in common: main colours (with shares), favourite shapes, motifs in the titles."""
    colours, shapes, words = Counter(), Counter(), Counter()
    for c in rows:
        col, sh = measure(_read(c))
        total = sum(col.values()) or 1
        for k, v in col.items():  # each drawing counts the same, however many shapes it has
            colours[k] += v / total
        for k in sh:
            shapes[k] += 1
        for w in set(re.findall(r"[a-z]{3,}", c["title"].lower())) - STOP:
            words[w[:-1] if w.endswith("s") and len(w) > 4 else w] += 1
    n = len(rows) or 1
    lively = {k: v for k, v in colours.items() if k not in ("white", "black", "grey")} or dict(colours)
    tot = sum(lively.values()) or 1
    return {
        "n": len(rows),
        "colours": [(k, round(v / tot, 2)) for k, v in sorted(lively.items(), key=lambda kv: -kv[1])[:4]],
        "shapes": [k for k, v in shapes.most_common(3) if v / n >= 0.3],
        "motifs": [w for w, v in words.most_common(4) if v >= 2],
    }


def distance(a: dict, b: dict) -> float:
    """0 = same palette, 1 = nothing in common."""
    da, dbb = dict(a["colours"]), dict(b["colours"])
    return round(1 - sum(min(da.get(k, 0), dbb.get(k, 0)) for k in set(da) | set(dbb)), 2)


def describe(f: dict) -> str:
    bits = []
    if f["colours"]:
        bits.append("mostly " + ", ".join(f"{k} ({round(v * 100)}%)" for k, v in f["colours"][:3]))
    if f["shapes"]:
        bits.append("lots of " + " and ".join(f["shapes"]))
    if f["motifs"]:
        bits.append("you keep drawing: " + ", ".join(f["motifs"]))
    return "; ".join(bits) or "hard to say yet"


# ---------------------------------------------------------------- periods

def current() -> dict | None:
    rows = db.q("SELECT * FROM art_periods WHERE ended IS NULL ORDER BY started DESC LIMIT 1")
    return rows[0] if rows else None


def _list(v, n: int, hexes: bool = False) -> list[str]:
    if isinstance(v, str):
        v = re.split(r"[,;\n]+", v)
    out = []
    for s in (v or [])[:8]:
        s = " ".join(str(s).split())[:40]
        if hexes:
            s = s.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", s) else ""
        if s and s not in out:
            out.append(s)
    return out[:n]


def start_period(a: dict) -> str:
    now = time.time()
    name = " ".join(str(a.get("name") or "").split())[:60]
    if not name:
        return "Give your new period a name, like 'the pond phase'."
    cur = current()
    if cur and now - cur["started"] < MIN_PERIOD_DAYS * DAY and not a.get("rename"):
        return (f"'{cur['name']}' only began {round((now - cur['started']) / 3600)} hours ago. Periods are long: "
                "give it a few days. (You can rename it with rename=true.)")
    palette, symbols, shapes = _list(a.get("palette"), 6, True), _list(a.get("symbols"), 6), _list(a.get("shapes"), 4)
    why = " ".join(str(a.get("why") or "").split())[:500]
    if cur and a.get("rename"):
        db.x("UPDATE art_periods SET name=?, why=COALESCE(NULLIF(?,''),why), palette=?, symbols=?, shapes=? "
             "WHERE id=?", (name, why, json.dumps(palette or json.loads(cur["palette"])),
                           json.dumps(symbols or json.loads(cur["symbols"])),
                           json.dumps(shapes or json.loads(cur["shapes"])), cur["id"]))
        return f"Your current period is now called '{name}'."
    if cur:
        db.x("UPDATE art_periods SET ended=? WHERE id=?", (now, cur["id"]))
    pid = db.x("INSERT INTO art_periods(started,name,why,palette,symbols,shapes) VALUES(?,?,?,?,?,?)",
               (now, name, why, json.dumps(palette), json.dumps(symbols), json.dumps(shapes)))
    db.event("create", f"began a new art period: {name}" + (f" (after '{cur['name']}')" if cur else ""))
    db.x("INSERT INTO memories(ts,text,importance,tags) VALUES(?,?,?,?)",
         (now, f"My art entered a new period: '{name}'. {why}"[:1000], 3, "art"))
    return f"A new chapter in your art: '{name}'." + (f" '{cur['name']}' is behind you now." if cur else "")


def tag(creation_id: int) -> None:
    """File a new drawing under the current period."""
    cur = current()
    if cur:
        db.x("UPDATE creations SET period_id=? WHERE id=?", (cur["id"], creation_id))


def _drawings(where: str = "", args: tuple = (), limit: int = 400) -> list[dict]:
    return db.q(f"SELECT id,ts,title,filename,period_id,dream_id FROM creations WHERE kind='svg' {where} "
                f"ORDER BY ts DESC LIMIT {int(limit)}", args)


def context_lines(now: float | None = None) -> str:
    now = now or time.time()
    recent = _drawings(limit=6)
    if not recent:
        return ""
    cur = current()
    lately = fingerprint(recent)
    out = ["\n## Your art style"]
    if cur:
        days = (now - cur["started"]) / DAY
        n = db.q("SELECT COUNT(*) AS n FROM creations WHERE kind='svg' AND period_id=?", (cur["id"],))[0]["n"]
        out.append(f"Period: '{cur['name']}' ({'since today' if days < 1 else f'{round(days)} day' + ('s' if round(days) != 1 else '')}, {n} drawings)"
                   + (f". Why: {cur['why']}" if cur["why"] else ""))
        chosen = [f"palette {' '.join(json.loads(cur['palette']))}" if cur["palette"] != "[]" else "",
                  f"symbols: {', '.join(json.loads(cur['symbols']))}" if cur["symbols"] != "[]" else "",
                  f"shapes: {', '.join(json.loads(cur['shapes']))}" if cur["shapes"] != "[]" else ""]
        if any(chosen):
            out.append("You chose: " + "; ".join(c for c in chosen if c))
    out.append(f"Your last {lately['n']} drawings: {describe(lately)}.")
    out.append("Draw in your own style (it's what makes a drawing a Gino), unless you're deliberately trying "
               "something new.")
    total = db.q("SELECT COUNT(*) AS n FROM creations WHERE kind='svg'")[0]["n"]
    if not cur and total >= 3:
        out.append("You haven't named your art period yet. When you know what your art is about right now, name it "
                   "with art_period (like 'the pond phase'): its palette, symbols and shapes.")
    elif cur and now - cur["started"] > 5 * DAY:
        mine = {r["id"] for r in recent}
        first = [r for r in reversed(_drawings("AND period_id=?", (cur["id"],))) if r["id"] not in mine][:6]
        if len(first) >= 3 and lately["n"] >= 4 and distance(fingerprint(first), lately) >= 0.5:
            out.append(f"Your drawings have been changing: '{cur['name']}' began {describe(fingerprint(first))}. "
                       "Is a new period starting? If it feels like it, name it with art_period.")
    return "\n".join(out)


# ---------------------------------------------------------------- browsing the periods

def overview(public_only: bool) -> list[dict]:
    """Every period, newest first, with what its drawings look like. public_only: just what's already public."""
    out = []
    periods = db.q("SELECT * FROM art_periods ORDER BY started DESC")
    for p in periods:
        rows = _drawings("AND period_id=?", (p["id"],))
        shown = rows
        if public_only:
            pub = {r["creation_id"] for r in db.q("SELECT creation_id FROM posts WHERE kind='page' AND creation_id "
                                                  "IS NOT NULL")}
            shown = [r for r in rows if r["id"] in pub]
        f = fingerprint(rows)
        out.append({"id": p["id"], "name": p["name"], "why": p["why"], "started": p["started"], "ended": p["ended"],
                    "palette": json.loads(p["palette"]), "symbols": json.loads(p["symbols"]),
                    "shapes": json.loads(p["shapes"]), "count": len(rows), "colours": f["colours"],
                    "drawings": [{"id": r["id"], "title": r["title"], "filename": r["filename"],
                                  "dream": bool(r["dream_id"])} for r in shown[:24]]})
    return out


SWATCH = {"red": "#d9463e", "orange": "#f08a2c", "yellow": "#f2c94c", "green": "#5aa86b", "teal": "#2fa3a0",
          "blue": "#3f7fd6", "purple": "#8a5cc9", "pink": "#e276a8", "brown": "#8a5a33", "white": "#f6f1e6",
          "black": "#2a2420", "grey": "#9a948c"}


def _date(ts) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(ts).strftime("%d %b %Y").lstrip("0")


@router.get("/blog/periods", response_class=HTMLResponse)
def periods_page():
    E = public.E
    ps = overview(public_only=True)
    parts = ['<h2 class="sec">Gino\'s art, period by period</h2>',
             '<p class="meta">Like any artist, Gino goes through phases: colours he can\'t stop using, shapes and '
             'symbols that keep coming back. He names each period himself.</p>']
    if not ps:
        parts.append('<p class="empty">Gino hasn\'t named an art period yet. Check back soon!</p>')
    for p in ps:
        name = p["name"] if not public.check(p["name"]) else "A period without a name"
        when = f"{_date(p['started'])} – {_date(p['ended']) if p['ended'] else 'now'}"
        why = p["why"] if p["why"] and not public.check(p["why"]) else ""
        swatches = "".join(f'<i style="background:{c}" title="{E(c)}"></i>' for c in p["palette"]) or "".join(
            f'<i style="background:{SWATCH.get(k, "#ccc")};flex:{max(v, .08)}" title="{E(k)}"></i>'
            for k, v in p["colours"])
        symbols = [s for s in p["symbols"] if not public.check(s)]
        art = "".join(f'<a class="tile" href="/blog/art/{d["id"]}.svg"><img src="/blog/art/{d["id"]}.svg" alt="'
                      f'{E(d["title"])}" loading="lazy"><strong>{"🌙 " if d["dream"] else ""}{E(d["title"])}</strong></a>'
                      for d in p["drawings"] if not public.check(d["title"]))
        parts.append(
            f'<div class="post period"><h3>{E(name)}</h3><div class="meta">{when} · {p["count"]} drawing'
            f'{"s" if p["count"] != 1 else ""}</div>'
            + (f'<div class="swatch">{swatches}</div>' if swatches else "")
            + (f'<p class="ex">{E(why)}</p>' if why else "")
            + (f'<p class="meta">Keeps coming back: {E(", ".join(symbols))}</p>' if symbols else "")
            + (f'<div class="grid" style="margin-top:12px">{art}</div>' if art else
               '<p class="meta">None of this period\'s drawings are on his website yet.</p>')
            + "</div>")
    css = ("<style>.swatch{display:flex;height:16px;border-radius:8px;overflow:hidden;margin:10px 0;max-width:320px}"
           ".swatch i{flex:1}.period .tile img{aspect-ratio:1}</style>")
    return public._page("Gino's art periods", css + "\n".join(parts),
                        "The phases of Gino the capybara's art: his favourite colours, shapes and symbols over time.")
